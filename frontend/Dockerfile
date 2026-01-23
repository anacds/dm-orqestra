FROM node:22-alpine

RUN corepack enable && corepack prepare pnpm@10.14.0 --activate

WORKDIR /app

COPY package.json pnpm-lock.yaml ./
RUN pnpm install

COPY . ./

EXPOSE 3000

CMD ["pnpm", "dev"]

