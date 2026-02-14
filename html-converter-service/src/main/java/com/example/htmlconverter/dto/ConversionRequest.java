package com.example.htmlconverter.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Positive;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ConversionRequest {
    
    @NotBlank(message = "HTML content cannot be blank")
    private String htmlContent;
    
    @Positive(message = "Width must be positive")
    @Builder.Default
    private Integer width = 800;
    
    @Positive(message = "Height must be positive")
    @Builder.Default
    private Integer height = 600;
    
    @Positive(message = "Scale must be positive")
    @Builder.Default
    private Float scale = 0.5f;
    
    @Builder.Default
    private ImageFormat imageFormat = ImageFormat.PNG;
    

    public enum ImageFormat {
        PNG, JPEG
    }
}
