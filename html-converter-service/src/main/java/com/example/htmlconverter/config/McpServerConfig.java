package com.example.htmlconverter.config;

import com.example.htmlconverter.dto.ConversionRequest;
import com.example.htmlconverter.dto.ConversionResponse;
import com.example.htmlconverter.service.HtmlConversionService;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.modelcontextprotocol.server.McpServer;
import io.modelcontextprotocol.server.McpServerFeatures;
import io.modelcontextprotocol.server.McpSyncServer;
import io.modelcontextprotocol.server.transport.WebMvcSseServerTransportProvider;
import io.modelcontextprotocol.spec.McpSchema;
import io.modelcontextprotocol.spec.McpSchema.CallToolResult;
import io.modelcontextprotocol.spec.McpSchema.ServerCapabilities;
import io.modelcontextprotocol.spec.McpSchema.Tool;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.function.RouterFunction;
import org.springframework.web.servlet.function.ServerResponse;

import java.util.Map;

/**
 * MCP Server configuration for exposing HTML conversion as an MCP tool.
 * 
 * This allows AI agents to consume the HTML-to-image conversion service
 * through the Model Context Protocol, regardless of the underlying implementation.
 */
@Configuration
@Slf4j
public class McpServerConfig {

    private static final String TOOL_NAME = "convert_html_to_image";
    private static final String TOOL_DESCRIPTION = """
        Converts HTML content (email, webpage, or HTML fragment) to a Base64 encoded image.
        
        The tool automatically:
        - Decodes email encodings (Quoted-Printable, URL encoding, HTML entities)
        - Wraps HTML fragments in a valid XHTML document if needed
        - Renders the HTML to PDF, then converts to image
        - Scales the image according to the specified factor
        
        Returns the image as a Base64 string along with metadata about dimensions.
        """;

    private static final String INPUT_SCHEMA = """
        {
            "type": "object",
            "properties": {
                "htmlContent": {
                    "type": "string",
                    "description": "The HTML content to convert. Can be a complete HTML document or a fragment."
                },
                "scale": {
                    "type": "number",
                    "description": "Scale factor for the output image. 1.0 = original size, 0.5 = 50% size."
                },
                "imageFormat": {
                    "type": "string",
                    "description": "Output image format: PNG or JPEG."
                }
            },
            "required": ["htmlContent"]
        }
        """;

    /**
     * Creates the MCP transport provider using Server-Sent Events over WebMVC.
     * This provides the communication layer for the MCP protocol.
     */
    @Bean
    public WebMvcSseServerTransportProvider mcpTransportProvider(ObjectMapper objectMapper) {
        log.info("Initializing MCP SSE transport provider at /mcp");
        return new WebMvcSseServerTransportProvider(objectMapper, "/mcp/message");
    }

    /**
     * Exposes the MCP router function to handle MCP protocol requests.
     */
    @Bean
    public RouterFunction<ServerResponse> mcpRouterFunction(WebMvcSseServerTransportProvider transportProvider) {
        return transportProvider.getRouterFunction();
    }

    /**
     * Creates and configures the MCP Server with the HTML conversion tool.
     */
    @Bean
    public McpSyncServer mcpServer(
            WebMvcSseServerTransportProvider transportProvider,
            HtmlConversionService htmlConversionService,
            ObjectMapper objectMapper) {
        
        log.info("Initializing MCP Server with HTML conversion tool");

        // Create the tool specification
        var htmlToImageTool = createHtmlToImageTool(htmlConversionService, objectMapper);

        // Build and configure the MCP server
        McpSyncServer server = McpServer.sync(transportProvider)
            .serverInfo("html-converter", "1.0.0")
            .capabilities(ServerCapabilities.builder()
                .tools(true)  // Enable tool support
                .build())
            .tools(htmlToImageTool)
            .build();

        log.info("MCP Server initialized successfully. Tool '{}' is available.", TOOL_NAME);
        
        return server;
    }

    /**
     * Creates the HTML-to-image tool specification with its handler.
     */
    private McpServerFeatures.SyncToolSpecification createHtmlToImageTool(
            HtmlConversionService htmlConversionService,
            ObjectMapper objectMapper) {
        
        // Build the Tool using the constructor that accepts schema as String
        Tool tool = new McpSchema.Tool(TOOL_NAME, TOOL_DESCRIPTION, INPUT_SCHEMA);

        return new McpServerFeatures.SyncToolSpecification(
            tool,
            (exchange, arguments) -> {
                log.info("MCP tool '{}' invoked", TOOL_NAME);
                
                try {
                    // Extract arguments with defaults
                    String htmlContent = extractString(arguments, "htmlContent");
                    Float scale = extractFloat(arguments, "scale", 0.5f);
                    String format = extractString(arguments, "imageFormat", "PNG");
                    
                    log.debug("Converting HTML ({} chars) with scale={}, format={}", 
                              htmlContent.length(), scale, format);

                    // Build the conversion request
                    ConversionRequest request = ConversionRequest.builder()
                        .htmlContent(htmlContent)
                        .scale(scale)
                        .imageFormat(ConversionRequest.ImageFormat.valueOf(format.toUpperCase()))
                        .build();

                    // Execute conversion
                    ConversionResponse response = htmlConversionService.convert(request);

                    // Build result JSON
                    String resultJson = objectMapper.writeValueAsString(Map.of(
                        "success", true,
                        "base64Image", response.getBase64Image(),
                        "imageFormat", response.getImageFormat(),
                        "originalWidth", response.getOriginalWidth(),
                        "originalHeight", response.getOriginalHeight(),
                        "reducedWidth", response.getReducedWidth(),
                        "reducedHeight", response.getReducedHeight(),
                        "fileSizeBytes", response.getFileSizeBytes()
                    ));

                    log.info("MCP tool '{}' completed successfully. Output: {}x{}", 
                             TOOL_NAME, response.getReducedWidth(), response.getReducedHeight());

                    return CallToolResult.builder()
                        .addTextContent(resultJson)
                        .isError(false)
                        .build();

                } catch (Exception e) {
                    log.error("MCP tool '{}' failed: {}", TOOL_NAME, e.getMessage(), e);
                    
                    String errorJson = String.format(
                        "{\"success\": false, \"error\": \"%s\"}", 
                        e.getMessage().replace("\"", "\\\"")
                    );
                    
                    return CallToolResult.builder()
                        .addTextContent(errorJson)
                        .isError(true)
                        .build();
                }
            }
        );
    }

    /**
     * Extracts a required string argument.
     */
    private String extractString(Map<String, Object> arguments, String key) {
        Object value = arguments.get(key);
        if (value == null) {
            throw new IllegalArgumentException("Required argument '" + key + "' is missing");
        }
        return value.toString();
    }

    /**
     * Extracts an optional string argument with a default value.
     */
    private String extractString(Map<String, Object> arguments, String key, String defaultValue) {
        Object value = arguments.get(key);
        return value != null ? value.toString() : defaultValue;
    }

    /**
     * Extracts an optional float argument with a default value.
     */
    private Float extractFloat(Map<String, Object> arguments, String key, Float defaultValue) {
        Object value = arguments.get(key);
        if (value == null) {
            return defaultValue;
        }
        if (value instanceof Number) {
            return ((Number) value).floatValue();
        }
        return Float.parseFloat(value.toString());
    }
}
