import logging
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import psycopg
import psycopg_pool
from app.core.config import settings
from langgraph.checkpoint.postgres import PostgresSaver as SyncPostgresSaver

logger = logging.getLogger(__name__)

_checkpoint_pool: psycopg_pool.AsyncConnectionPool | None = None
_checkpoint_saver: AsyncPostgresSaver | None = None
_setup_done: bool = False


def _check_tables_exist(conn) -> bool:
    """Check if checkpoints table already exists."""
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.checkpoints')")
        result = cur.fetchone()
        return result is not None and result[0] is not None


def _run_setup_with_autocommit():
    """
    Run PostgresSaver.setup() with autocommit enabled.
    
    CREATE INDEX CONCURRENTLY cannot run inside a transaction block,
    so we need a separate connection with autocommit=True for setup.
    Only runs if tables don't exist yet.
    """
    global _setup_done
    
    if _setup_done:
        return
    
    logger.info("Checking if checkpoints tables exist...")
    
    
    with psycopg.connect(settings.DATABASE_URL, autocommit=True) as conn:

        if _check_tables_exist(conn):
            logger.info("Checkpoints tables already exist, skipping setup")
            _setup_done = True
            return
        
        logger.info("Running AsyncPostgresSaver setup with autocommit...")
        saver = SyncPostgresSaver(conn)
        saver.setup()
        logger.info("PostgresSaver tables and indexes created/verified")
    
    _setup_done = True


async def get_checkpoint_pool() -> psycopg_pool.AsyncConnectionPool:
    """Get or create the async connection pool for checkpointing."""
    global _checkpoint_pool
    
    if _checkpoint_pool is None:
        logger.info("Initializing async checkpoint connection pool...")
        _checkpoint_pool = psycopg_pool.AsyncConnectionPool(
            conninfo=settings.DATABASE_URL,
            min_size=1,
            max_size=10,
            open=False
        )
        await _checkpoint_pool.open()
        logger.info("Async checkpoint connection pool initialized")
    
    return _checkpoint_pool


async def get_checkpoint_saver() -> AsyncPostgresSaver:
    """
    Get AsyncPostgresSaver instance for checkpointing.
    
    Creates an AsyncPostgresSaver with an async connection pool.
    The saver will be reused across multiple graph executions.
    """
    global _checkpoint_saver
    
    if _checkpoint_saver is None:
        logger.info("Initializing AsyncPostgresSaver...")
        
        _run_setup_with_autocommit()
        pool = await get_checkpoint_pool()

        try:
            _checkpoint_saver = AsyncPostgresSaver(pool)
            logger.info("AsyncPostgresSaver initialized successfully with async connection pool")
        except Exception as e:
            logger.error(f"Failed to create AsyncPostgresSaver: {e}", exc_info=True)
            raise
    
    return _checkpoint_saver


async def close_checkpoint_pool():
    global _checkpoint_pool, _checkpoint_saver, _setup_done
    
    _checkpoint_saver = None
    
    if _checkpoint_pool is not None:
        await _checkpoint_pool.close()
        _checkpoint_pool = None
        _setup_done = False
        logger.info("Async checkpoint connection pool closed")

