package com.example.htmlconverter.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ConversionResponse {

    private String base64Image;
    private String imageFormat;
    private Integer originalWidth;
    private Integer originalHeight;
    private Integer reducedWidth;
    private Integer reducedHeight;
    private Long fileSizeBytes;
}
