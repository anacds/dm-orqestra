package com.example.htmlconverter.service;

import com.example.htmlconverter.exception.ConversionException;
import lombok.extern.slf4j.Slf4j;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.PDFRenderer;
import org.springframework.stereotype.Service;

import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.Base64;

/**
 * Service responsible for image processing operations.
 */
@Service
@Slf4j
public class ImageProcessingService {

    private static final int DEFAULT_DPI = 300;

    /**
     * Converts a PDF document to a BufferedImage.
     * 
     * @param pdfBytes The PDF content as bytes
     * @return BufferedImage of the first page
     */
    public BufferedImage convertPdfToImage(byte[] pdfBytes) {
        try (PDDocument document = Loader.loadPDF(pdfBytes)) {
            PDFRenderer pdfRenderer = new PDFRenderer(document);
            BufferedImage image = pdfRenderer.renderImageWithDPI(0, DEFAULT_DPI);
            log.debug("PDF converted to image: {}x{}", image.getWidth(), image.getHeight());
            return image;
        } catch (IOException e) {
            throw new ConversionException("Failed to convert PDF to image", e);
        }
    }

    /**
     * Reduces the size of an image by applying a scale factor.
     * 
     * @param originalImage The original image
     * @param scale Scale factor (0.5 = 50% of original size)
     * @return Scaled image
     */
    public BufferedImage scaleImage(BufferedImage originalImage, float scale) {
        int newWidth = Math.round(originalImage.getWidth() * scale);
        int newHeight = Math.round(originalImage.getHeight() * scale);
        
        BufferedImage scaledImage = new BufferedImage(
            newWidth, 
            newHeight, 
            BufferedImage.TYPE_INT_RGB
        );
        
        Graphics2D graphics = scaledImage.createGraphics();
        configureHighQualityRendering(graphics);
        
        graphics.drawImage(originalImage, 0, 0, newWidth, newHeight, null);
        graphics.dispose();
        
        log.debug("Image scaled from {}x{} to {}x{}", 
                  originalImage.getWidth(), originalImage.getHeight(),
                  newWidth, newHeight);
        
        return scaledImage;
    }

    /**
     * Converts a BufferedImage to a Base64 encoded string.
     * 
     * @param image The image to convert
     * @param format The output format (PNG, JPEG)
     * @return Base64 encoded image string
     */
    public String convertToBase64(BufferedImage image, String format) {
        try {
            ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
            ImageIO.write(image, format.toUpperCase(), outputStream);
            byte[] imageBytes = outputStream.toByteArray();
            
            String base64 = Base64.getEncoder().encodeToString(imageBytes);
            log.debug("Image converted to Base64, size: {} bytes", base64.length());
            
            return base64;
        } catch (IOException e) {
            throw new ConversionException("Failed to convert image to Base64", e);
        }
    }

    private void configureHighQualityRendering(Graphics2D graphics) {
        graphics.setRenderingHint(
            RenderingHints.KEY_INTERPOLATION, 
            RenderingHints.VALUE_INTERPOLATION_BILINEAR
        );
        graphics.setRenderingHint(
            RenderingHints.KEY_RENDERING, 
            RenderingHints.VALUE_RENDER_QUALITY
        );
        graphics.setRenderingHint(
            RenderingHints.KEY_ANTIALIASING, 
            RenderingHints.VALUE_ANTIALIAS_ON
        );
    }
}
