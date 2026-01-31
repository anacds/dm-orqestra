package com.example.htmlconverter.controller;

import com.example.htmlconverter.dto.ConversionRequest;
import com.example.htmlconverter.dto.ConversionResponse;
import com.example.htmlconverter.service.HtmlConversionService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * REST controller for HTML to image conversion operations.
 */
@RestController
@RequestMapping("/api/v1/html-to-image")
@RequiredArgsConstructor
@Slf4j
public class HtmlConverterController {

    private final HtmlConversionService conversionService;

    /**
     * Converts HTML content to a Base64 encoded image.
     * 
     * @param request The conversion request
     * @return ConversionResponse with the Base64 image
     */
    @PostMapping("/convert")
    public ResponseEntity<ConversionResponse> convert(@Valid @RequestBody ConversionRequest request) {
        log.info("Received conversion request");
        ConversionResponse response = conversionService.convert(request);
        return ResponseEntity.ok(response);
    }

    /**
     * Health check endpoint.
     */
    @GetMapping("/health")
    public ResponseEntity<String> health() {
        return ResponseEntity.ok("HTML to Image API is running");
    }
}
