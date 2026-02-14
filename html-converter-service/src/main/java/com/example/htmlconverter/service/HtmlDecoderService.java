package com.example.htmlconverter.service;

import lombok.extern.slf4j.Slf4j;
import org.apache.commons.codec.DecoderException;
import org.apache.commons.codec.net.QuotedPrintableCodec;
import org.apache.commons.codec.net.URLCodec;
import org.apache.commons.text.StringEscapeUtils;
import org.springframework.stereotype.Service;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.regex.Pattern;


@Service
@Slf4j
public class HtmlDecoderService {

    private static final Pattern URL_ENCODED_PATTERN = Pattern.compile("%[0-9A-Fa-f]{2}");
    private static final Pattern QUOTED_PRINTABLE_PATTERN = Pattern.compile("=[0-9A-Fa-f]{2}");
    private static final Pattern QP_SOFT_LINE_BREAK_PATTERN = Pattern.compile("=\\r?\\n");
    private static final Pattern BASE64_PATTERN = Pattern.compile("^[A-Za-z0-9+/]+=*$");
    
    private static final double URL_ENCODING_THRESHOLD = 0.05;
    private static final double QP_ENCODING_THRESHOLD = 0.02;
    private static final int MAX_DECODE_ITERATIONS = 5;

    private final QuotedPrintableCodec qpCodec;
    private final URLCodec urlCodec;

    public HtmlDecoderService() {
        this.qpCodec = new QuotedPrintableCodec(StandardCharsets.UTF_8);
        this.urlCodec = new URLCodec(StandardCharsets.UTF_8.name());
    }

    public String decode(String content) {
        if (content == null || content.isEmpty()) {
            return content;
        }

        log.debug("Starting HTML decoding, input length: {}", content.length());
        String result = content;
        int iterations = 0;

        while (iterations < MAX_DECODE_ITERATIONS) {
            String previousResult = result;
            
            if (isUrlEncoded(result)) {
                log.debug("Detected URL encoding, applying decoder");
                result = decodeUrl(result);
            }
            
            if (hasHtmlEntities(result)) {
                log.debug("Detected HTML entities, applying decoder");
                result = decodeHtmlEntities(result);
            }
            
            if (isQuotedPrintable(result)) {
                log.debug("Detected Quoted-Printable encoding, applying decoder");
                result = decodeQuotedPrintable(result);
            }
            
            if (result.equals(previousResult)) {
                break;
            }
            
            iterations++;
        }

        log.debug("HTML decoding completed after {} iterations, output length: {}", 
                  iterations, result.length());
        return result;
    }


    public String decodeBase64Content(String content) {
        if (isBase64Encoded(content)) {
            return decodeBase64(content);
        }
        return content;
    }

    private boolean isUrlEncoded(String content) {
        if (content == null || content.length() < 3) {
            return false;
        }
        
        long matches = URL_ENCODED_PATTERN.matcher(content).results().count();
        double ratio = (matches * 3.0) / content.length();
        
        return ratio >= URL_ENCODING_THRESHOLD;
    }

    private boolean hasHtmlEntities(String content) {
        if (content == null) {
            return false;
        }
        
        return content.contains("&lt;") || 
               content.contains("&gt;") || 
               content.contains("&amp;") ||
               content.contains("&quot;") ||
               content.contains("&apos;") ||
               content.contains("&#");
    }

    private boolean isQuotedPrintable(String content) {
        if (content == null || content.length() < 3) {
            return false;
        }
        
        boolean hasQpPatterns = content.contains("=3D") || 
                                content.contains("=0A") || 
                                content.contains("=0D") ||
                                content.contains("=20");
        
        if (hasQpPatterns) {
            return true;
        }
        
        if (QP_SOFT_LINE_BREAK_PATTERN.matcher(content).find()) {
            return true;
        }
        
        long matches = QUOTED_PRINTABLE_PATTERN.matcher(content).results().count();
        double ratio = (matches * 3.0) / content.length();
        
        return ratio >= QP_ENCODING_THRESHOLD;
    }

    private boolean isBase64Encoded(String content) {
        if (content == null || content.length() < 20) {
            return false;
        }
        
        String trimmed = content.replaceAll("\\s+", "");
        
        return trimmed.length() % 4 == 0 && 
               BASE64_PATTERN.matcher(trimmed).matches();
    }

    private String decodeUrl(String content) {
        try {
            return urlCodec.decode(content);
        } catch (DecoderException e) {
            log.warn("URL decoding failed with UTF-8, trying ISO-8859-1: {}", e.getMessage());
            try {
                URLCodec latinCodec = new URLCodec("ISO-8859-1");
                return latinCodec.decode(content);
            } catch (DecoderException e2) {
                log.warn("URL decoding also failed with ISO-8859-1, returning original");
                return content;
            }
        }
    }

    private String decodeHtmlEntities(String content) {
        return StringEscapeUtils.unescapeHtml4(content);
    }

    private String decodeQuotedPrintable(String content) {
        try {
            String preprocessed = content.replaceAll("=\\r?\\n", "");
            byte[] decoded = qpCodec.decode(preprocessed.getBytes(StandardCharsets.UTF_8));
            return new String(decoded, StandardCharsets.UTF_8);
        } catch (DecoderException e) {
            log.warn("QP decoding failed with UTF-8, trying ISO-8859-1: {}", e.getMessage());
            try {
                QuotedPrintableCodec latinCodec = new QuotedPrintableCodec(
                    Charset.forName("ISO-8859-1")
                );
                String preprocessed = content.replaceAll("=\\r?\\n", "");
                byte[] decoded = latinCodec.decode(preprocessed.getBytes(StandardCharsets.ISO_8859_1));
                return new String(decoded, StandardCharsets.ISO_8859_1);
            } catch (DecoderException e2) {
                log.warn("QP decoding also failed with ISO-8859-1, trying manual decode");
                return manualQuotedPrintableDecode(content);
            }
        }
    }

    private String manualQuotedPrintableDecode(String content) {
        StringBuilder result = new StringBuilder();
        String processed = content.replaceAll("=\\r?\\n", "");
        
        int i = 0;
        while (i < processed.length()) {
            char c = processed.charAt(i);
            
            if (c == '=' && i + 2 < processed.length()) {
                String hex = processed.substring(i + 1, i + 3);
                if (hex.matches("[0-9A-Fa-f]{2}")) {
                    try {
                        int value = Integer.parseInt(hex, 16);
                        result.append((char) value);
                        i += 3;
                        continue;
                    } catch (NumberFormatException e) {
                        // Not a valid hex sequence, treat as literal
                    }
                }
            }
            
            result.append(c);
            i++;
        }
        
        return result.toString();
    }

    private String decodeBase64(String content) {
        try {
            String trimmed = content.replaceAll("\\s+", "");
            byte[] decoded = Base64.getDecoder().decode(trimmed);
            
            String result = new String(decoded, StandardCharsets.UTF_8);
            
            if (result.chars().filter(c -> c < 32 && c != '\n' && c != '\r' && c != '\t')
                       .count() > result.length() * 0.1) {
                log.warn("Base64 decoded content appears to be binary, returning original");
                return content;
            }
            
            return result;
        } catch (IllegalArgumentException e) {
            log.warn("Base64 decoding failed: {}", e.getMessage());
            return content;
        }
    }
}
