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


@Service
@Slf4j
@RequiredArgsConstructor
public class HtmlConversionService {

    private final HtmlDecoderService htmlDecoderService;
    private final ImageProcessingService imageProcessingService;

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

    private String ensureWellFormedHtml(String htmlContent) {
        String trimmed = htmlContent.trim();
        
        String lowerTrimmed = trimmed.toLowerCase();
        if (!lowerTrimmed.contains("<html") && !lowerTrimmed.contains("<body")) {
            htmlContent = wrapFragment(trimmed);
        }
        
        Document doc = Jsoup.parse(htmlContent);
        
        doc.outputSettings()
            .syntax(Document.OutputSettings.Syntax.xml)  // XHTML syntax
            .escapeMode(Entities.EscapeMode.xhtml)       // XHTML entities
            .charset("UTF-8");
        
        String xhtml = doc.html();
        String result = buildXhtmlDocument(xhtml);
        
        log.debug("HTML converted to XHTML ({} chars)", result.length());
        return result;
    }

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


    private String buildXhtmlDocument(String htmlContent) {
        String content = htmlContent
            .replaceFirst("(?i)<!DOCTYPE[^>]*>", "")
            .replaceFirst("<\\?xml[^>]*\\?>", "")
            .trim();
        
        if (!content.contains("xmlns=")) {
            content = content.replaceFirst("(?i)<html([^>]*)>", "<html$1 xmlns=\"http://www.w3.org/1999/xhtml\">");
        }
        
        return """
            <?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" 
                "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
            %s
            """.formatted(content);
    }
}
