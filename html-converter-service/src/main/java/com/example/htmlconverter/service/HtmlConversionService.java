package com.example.htmlconverter.service;

import com.example.htmlconverter.dto.ConversionRequest;
import com.example.htmlconverter.dto.ConversionResponse;
import com.example.htmlconverter.exception.ConversionException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Entities;
import org.springframework.stereotype.Service;
import org.xhtmlrenderer.pdf.ITextRenderer;

import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;

/**
 * Main service that orchestrates the HTML to image conversion process.
 * 
 * Flow: HTML → Decode → PDF → Image → Scale → Base64
 */
@Service
@Slf4j
@RequiredArgsConstructor
public class HtmlConversionService {

    private final HtmlDecoderService htmlDecoderService;
    private final ImageProcessingService imageProcessingService;

    /**
     * Converts HTML content to a Base64 encoded image.
     * 
     * @param request The conversion request containing HTML and options
     * @return ConversionResponse with the Base64 image and metadata
     */
    public ConversionResponse convert(ConversionRequest request) {
        log.info("Starting HTML to image conversion");
        
        try {
            // Step 1: Decode any email encodings
            String decodedHtml = htmlDecoderService.decode(request.getHtmlContent());
            log.debug("HTML decoded successfully");
            
            // Step 2: Ensure HTML is well-formed and convert to PDF
            String wellFormedHtml = ensureWellFormedHtml(decodedHtml);
            byte[] pdfBytes = convertHtmlToPdf(wellFormedHtml);
            log.debug("HTML converted to PDF, size: {} bytes", pdfBytes.length);
            
            // Step 3: Convert PDF to image
            BufferedImage originalImage = imageProcessingService.convertPdfToImage(pdfBytes);
            
            // Step 4: Scale the image
            BufferedImage scaledImage = imageProcessingService.scaleImage(
                originalImage, 
                request.getScale()
            );
            
            // Step 5: Convert to Base64
            String formatName = request.getImageFormat().name();
            String base64Image = imageProcessingService.convertToBase64(scaledImage, formatName);
            
            // Build response
            ConversionResponse response = ConversionResponse.builder()
                .base64Image(base64Image)
                .imageFormat(formatName)
                .originalWidth(originalImage.getWidth())
                .originalHeight(originalImage.getHeight())
                .reducedWidth(scaledImage.getWidth())
                .reducedHeight(scaledImage.getHeight())
                .fileSizeBytes((long) base64Image.length())
                .build();
            
            log.info("Conversion completed successfully. Output: {}x{}", 
                     response.getReducedWidth(), response.getReducedHeight());
            
            return response;
            
        } catch (ConversionException e) {
            throw e;
        } catch (Exception e) {
            log.error("Conversion failed", e);
            throw new ConversionException("Failed to convert HTML to image: " + e.getMessage(), e);
        }
    }

    private byte[] convertHtmlToPdf(String htmlContent) throws Exception {
        ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
        ITextRenderer renderer = new ITextRenderer();
        
        renderer.setDocumentFromString(htmlContent);
        renderer.layout();
        renderer.createPDF(outputStream);
        renderer.finishPDF();
        
        return outputStream.toByteArray();
    }

    /**
     * Converts any HTML (including HTML5) to valid XHTML for Flying Saucer.
     * 
     * Uses jsoup to:
     * - Parse and clean malformed HTML
     * - Convert to XHTML syntax (self-closing tags, lowercase, etc.)
     * - Add proper XML declaration and DOCTYPE
     */
    private String ensureWellFormedHtml(String htmlContent) {
        String trimmed = htmlContent.trim();
        
        // If it's just a fragment (no html/body), wrap it first
        String lowerTrimmed = trimmed.toLowerCase();
        if (!lowerTrimmed.contains("<html") && !lowerTrimmed.contains("<body")) {
            htmlContent = wrapFragment(trimmed);
        }
        
        // Parse with jsoup (handles malformed HTML gracefully)
        Document doc = Jsoup.parse(htmlContent);
        
        // Configure for XHTML output
        doc.outputSettings()
            .syntax(Document.OutputSettings.Syntax.xml)  // XHTML syntax
            .escapeMode(Entities.EscapeMode.xhtml)       // XHTML entities
            .charset("UTF-8");
        
        // Get the HTML content (jsoup adds proper structure)
        String xhtml = doc.html();
        
        // Add XML declaration and XHTML DOCTYPE
        String result = buildXhtmlDocument(xhtml);
        
        log.debug("HTML converted to XHTML ({} chars)", result.length());
        return result;
    }

    /**
     * Wraps an HTML fragment in a basic HTML structure.
     */
    private String wrapFragment(String content) {
        return """
            <html>
            <head>
                <meta charset="UTF-8" />
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; }
                </style>
            </head>
            <body>
                %s
            </body>
            </html>
            """.formatted(content);
    }

    /**
     * Builds a complete XHTML document with proper declarations.
     */
    private String buildXhtmlDocument(String htmlContent) {
        // Remove any existing DOCTYPE or XML declaration that jsoup might have added
        String content = htmlContent
            .replaceFirst("(?i)<!DOCTYPE[^>]*>", "")
            .replaceFirst("<\\?xml[^>]*\\?>", "")
            .trim();
        
        // Ensure <html> has xmlns attribute
        if (!content.contains("xmlns=")) {
            content = content.replaceFirst("(?i)<html([^>]*)>", "<html$1 xmlns=\"http://www.w3.org/1999/xhtml\">");
        }
        
        // Build complete XHTML document
        return """
            <?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" 
                "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
            %s
            """.formatted(content);
    }
}
