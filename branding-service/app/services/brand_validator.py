"""
Brand Validator Service - Validates HTML email against Orqestra brand guidelines.

This is a deterministic validation service (no AI/LLM).
"""

import re
from typing import List, Dict, Any
from dataclasses import dataclass
from bs4 import BeautifulSoup


@dataclass
class Violation:
    """Represents a brand guideline violation."""
    rule: str
    category: str
    severity: str  # 'critical', 'warning', 'info'
    value: str = ""
    message: str = ""


class BrandValidator:
    """Validates HTML email against Orqestra brand guidelines."""
    
    # Brand colors
    APPROVED_COLORS = {
        # Primary brand colors
        '#6B7FFF', '#6b7fff',
        '#8B9FFF', '#8b9fff',
        
        # Neutral backgrounds
        '#FFFFFF', '#ffffff',
        '#F5F5F5', '#f5f5f5',
        '#F8F9FF', '#f8f9ff',
        
        # Text colors
        '#333333', '#333',
        '#555555', '#555',
        '#666666', '#666',
        '#888888', '#888',
        '#999999', '#999',
        '#CCCCCC', '#ccc',
        
        # Dark variations
        '#000000', '#000',
        '#1A1A1A',
        '#2A2A2A',
        '#0A0A0A',
    }
    
    # Primary colors (must be present)
    PRIMARY_COLORS = {'#6B7FFF', '#6b7fff', '#8B9FFF', '#8b9fff'}
    
    # Approved fonts
    APPROVED_FONTS = ['arial', 'helvetica', 'sans-serif']
    
    # Prohibited fonts
    PROHIBITED_FONTS = [
        'times', 'times new roman', 'georgia', 'serif',
        'comic sans', 'comic sans ms',
        'courier', 'courier new',
        'impact',
        'papyrus', 'brush script'
    ]
    
    def __init__(self):
        self.violations: List[Violation] = []
    
    def validate(self, html: str) -> Dict[str, Any]:
        """
        Main validation method.
        
        Args:
            html: HTML string to validate
            
        Returns:
            Dictionary with validation results
        """
        self.violations = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract all styles
        inline_styles = self._extract_inline_styles(soup)
        style_tag_css = self._extract_style_tags(soup)
        all_styles = inline_styles + '\n' + style_tag_css
        
        # Run validations
        self._validate_colors(all_styles, soup)
        self._validate_fonts(all_styles)
        self._validate_logo(soup)
        self._validate_layout(soup)
        self._validate_ctas(soup)
        self._validate_footer(soup)
        self._validate_prohibited_elements(all_styles, html)
        
        return self._generate_report()
    
    def _extract_inline_styles(self, soup: BeautifulSoup) -> str:
        """Extract all inline styles from HTML."""
        styles = []
        for element in soup.find_all(style=True):
            styles.append(element.get('style', ''))
        return ' '.join(styles)
    
    def _extract_style_tags(self, soup: BeautifulSoup) -> str:
        """Extract CSS from <style> tags."""
        style_tags = soup.find_all('style')
        return '\n'.join([tag.string or '' for tag in style_tags])
    
    def _normalize_color(self, color: str) -> str:
        """Normalize color to hex format."""
        color = color.strip().lower()
        
        # Convert rgb/rgba to hex
        rgb_match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)', color)
        if rgb_match:
            r, g, b = map(int, rgb_match.groups())
            return f'#{r:02x}{g:02x}{b:02x}'
        
        # Ensure # prefix
        if not color.startswith('#'):
            color = '#' + color
        
        # Expand shorthand (#fff -> #ffffff)
        if len(color) == 4:
            color = '#' + ''.join([c*2 for c in color[1:]])
        
        return color
    
    def _extract_colors(self, css: str) -> List[str]:
        """Extract all colors from CSS."""
        colors = set()
        
        # Hex colors
        hex_colors = re.findall(r'#[0-9a-fA-F]{3,6}', css)
        colors.update(hex_colors)
        
        # RGB/RGBA colors
        rgb_colors = re.findall(r'rgba?\([^)]+\)', css)
        colors.update(rgb_colors)
        
        return [self._normalize_color(c) for c in colors]
    
    def _validate_colors(self, css: str, soup: BeautifulSoup):
        """Validate color usage."""
        used_colors = self._extract_colors(css)
        
        for color in used_colors:
            normalized = self._normalize_color(color)
            if normalized not in self.APPROVED_COLORS:
                # Skip transparent and very light grays
                if normalized not in ['#000000', '#ffffff'] and not re.match(r'#[ef][ef][ef][ef][ef][ef]', normalized):
                    self.violations.append(Violation(
                        rule='unapproved_color',
                        category='colors',
                        severity='critical',
                        value=color,
                        message=f'Cor {color} não está na paleta aprovada da marca'
                    ))
        
        # Check if primary color is present
        has_primary = any(
            self._normalize_color(c) in self.PRIMARY_COLORS 
            for c in used_colors
        )
        
        if not has_primary:
            self.violations.append(Violation(
                rule='missing_primary_color',
                category='colors',
                severity='warning',
                message='Cor primária da marca (#6B7FFF) não está presente'
            ))
    
    def _validate_fonts(self, css: str):
        """Validate font usage."""
        font_families = re.findall(r'font-family\s*:\s*([^;]+)', css, re.IGNORECASE)
        
        for font_family in font_families:
            normalized = font_family.lower().replace('"', '').replace("'", '')
            
            # Check for prohibited fonts
            for prohibited in self.PROHIBITED_FONTS:
                if prohibited in normalized:
                    self.violations.append(Violation(
                        rule='prohibited_font',
                        category='typography',
                        severity='critical',
                        value=font_family.strip(),
                        message=f'Fonte proibida detectada: {prohibited}'
                    ))
                    break
            
            # Check if uses approved fonts
            fonts = [f.strip() for f in normalized.split(',')]
            has_approved = any(f in self.APPROVED_FONTS for f in fonts)
            
            if not has_approved and not any(prohibited in normalized for prohibited in self.PROHIBITED_FONTS):
                self.violations.append(Violation(
                    rule='unapproved_font',
                    category='typography',
                    severity='warning',
                    value=font_family.strip(),
                    message='Fonte não está na lista de fontes aprovadas'
                ))
        
        # Check font sizes
        font_sizes = re.findall(r'font-size\s*:\s*(\d+)px', css, re.IGNORECASE)
        for size_str in font_sizes:
            size = int(size_str)
            if size < 12:
                self.violations.append(Violation(
                    rule='font_size_too_small',
                    category='typography',
                    severity='warning',
                    value=f'{size}px',
                    message=f'Tamanho de fonte muito pequeno: {size}px (mínimo 12px)'
                ))
    
    def _validate_logo(self, soup: BeautifulSoup):
        """Validate logo presence and attributes."""
        logo_candidates = (
            soup.find_all('img', class_=re.compile(r'logo', re.IGNORECASE)) +
            soup.find_all('img', id=re.compile(r'logo', re.IGNORECASE)) +
            soup.find_all('img', alt=re.compile(r'orqestra', re.IGNORECASE))
        )
        
        header = soup.find(['header', 'div'], class_=re.compile(r'header', re.IGNORECASE))
        if header:
            logo_candidates.extend(header.find_all('img'))
        
        if not logo_candidates:
            self.violations.append(Violation(
                rule='missing_logo',
                category='logo',
                severity='critical',
                message='Logo da Orqestra não encontrado no email'
            ))
            return
        
        for logo in logo_candidates[:1]:
            height_attr = logo.get('height', '')
            style = logo.get('style', '')
            height_match = re.search(r'height\s*:\s*(\d+)px', style)
            
            height = None
            if height_attr:
                height = int(height_attr)
            elif height_match:
                height = int(height_match.group(1))
            
            if height:
                if height < 40:
                    self.violations.append(Violation(
                        rule='logo_too_small',
                        category='logo',
                        severity='warning',
                        value=f'{height}px',
                        message=f'Logo muito pequeno: {height}px (mínimo 40px)'
                    ))
                elif height > 80:
                    self.violations.append(Violation(
                        rule='logo_too_large',
                        category='logo',
                        severity='warning',
                        value=f'{height}px',
                        message=f'Logo muito grande: {height}px (máximo 80px)'
                    ))
            
            alt = logo.get('alt', '').lower()
            if 'orqestra' not in alt:
                self.violations.append(Violation(
                    rule='missing_logo_alt_text',
                    category='logo',
                    severity='warning',
                    message='Logo sem alt text "Orqestra" adequado'
                ))
    
    def _validate_layout(self, soup: BeautifulSoup):
        """Validate layout structure."""
        container = (
            soup.find('div', class_=re.compile(r'container|email-container', re.IGNORECASE)) or
            soup.find('table', role='presentation')
        )
        
        if container:
            style = container.get('style', '')
            width_match = re.search(r'max-width\s*:\s*(\d+)px', style)
            width_attr = container.get('width', '')
            
            width = None
            if width_match:
                width = int(width_match.group(1))
            elif width_attr:
                width = int(width_attr)
            
            if width and width > 650:
                self.violations.append(Violation(
                    rule='container_too_wide',
                    category='layout',
                    severity='warning',
                    value=f'{width}px',
                    message=f'Container muito largo: {width}px (máximo recomendado 600px)'
                ))
        
        body = soup.find('body')
        if body:
            style = body.get('style', '')
            bg_match = re.search(r'background-color\s*:\s*([^;]+)', style)
            if bg_match:
                bg_color = self._normalize_color(bg_match.group(1))
                if bg_color not in ['#ffffff', '#f5f5f5', '#000000']:
                    self.violations.append(Violation(
                        rule='non_neutral_background',
                        category='layout',
                        severity='warning',
                        value=bg_color,
                        message='Background do body deve ser neutro (branco ou cinza claro)'
                    ))
    
    def _validate_ctas(self, soup: BeautifulSoup):
        """Validate Call-to-Action buttons."""
        ctas = (
            soup.find_all('a', class_=re.compile(r'cta|button', re.IGNORECASE)) +
            soup.find_all('a', style=re.compile(r'background', re.IGNORECASE))
        )
        
        for cta in ctas:
            style = cta.get('style', '')
            
            bg_match = re.search(r'background(?:-color)?\s*:\s*([^;]+)', style)
            if bg_match:
                bg_value = bg_match.group(1)
                if 'gradient' not in bg_value.lower():
                    bg_color = self._normalize_color(bg_value)
                    if bg_color not in self.PRIMARY_COLORS:
                        self.violations.append(Violation(
                            rule='cta_wrong_background_color',
                            category='cta',
                            severity='critical',
                            value=bg_color,
                            message=f'CTA deve usar cor primária (#6B7FFF), encontrado: {bg_color}'
                        ))
            
            color_match = re.search(r'(?<!background-)color\s*:\s*([^;]+)', style)
            if color_match:
                text_color = self._normalize_color(color_match.group(1))
                if text_color not in ['#ffffff', '#fff']:
                    self.violations.append(Violation(
                        rule='cta_wrong_text_color',
                        category='cta',
                        severity='warning',
                        value=text_color,
                        message='Texto do CTA deve ser branco (#FFFFFF)'
                    ))
    
    def _validate_footer(self, soup: BeautifulSoup):
        """Validate footer requirements."""
        footer = soup.find(['footer', 'div'], class_=re.compile(r'footer', re.IGNORECASE))
        
        if not footer:
            containers = soup.find_all('div', class_=True)
            if containers:
                footer = containers[-1]
        
        if not footer:
            self.violations.append(Violation(
                rule='missing_footer',
                category='footer',
                severity='critical',
                message='Footer não encontrado'
            ))
            return
        
        footer_text = footer.get_text().lower()
        
        has_copyright = '©' in footer.get_text() and 'orqestra' in footer_text
        if not has_copyright:
            self.violations.append(Violation(
                rule='missing_copyright',
                category='footer',
                severity='warning',
                message='Copyright "© 2026 Orqestra" não encontrado no footer'
            ))
        
        has_unsubscribe = any(keyword in footer_text for keyword in 
                             ['unsubscribe', 'descadastrar', 'cancelar', 'remover'])
        if not has_unsubscribe:
            self.violations.append(Violation(
                rule='missing_unsubscribe',
                category='footer',
                severity='warning',
                message='Link de descadastro não encontrado no footer'
            ))
    
    def _validate_prohibited_elements(self, css: str, html: str):
        """Validate prohibited styling elements."""
        if re.search(r'@keyframes.*blink', css, re.IGNORECASE | re.DOTALL):
            self.violations.append(Violation(
                rule='prohibited_blink_animation',
                category='prohibited',
                severity='critical',
                message='Animações "blink" são proibidas'
            ))
        
        text_shadows = re.findall(r'text-shadow\s*:\s*([^;]+)', css, re.IGNORECASE)
        for shadow in text_shadows:
            if shadow.strip() not in ['none', '0', '0px']:
                self.violations.append(Violation(
                    rule='prohibited_text_shadow',
                    category='prohibited',
                    severity='warning',
                    message='Text-shadow excessivo não é permitido'
                ))
        
        transforms = re.findall(r'transform\s*:\s*rotate\(([^)]+)\)', css, re.IGNORECASE)
        for transform in transforms:
            angle_match = re.search(r'(-?\d+)', transform)
            if angle_match:
                angle = abs(int(angle_match.group(1)))
                if angle > 2:
                    self.violations.append(Violation(
                        rule='prohibited_rotation',
                        category='prohibited',
                        severity='warning',
                        value=f'{angle}deg',
                        message=f'Rotação excessiva detectada: {angle}° (máximo 2°)'
                    ))
    
    def _generate_report(self) -> Dict[str, Any]:
        """Generate validation report."""
        critical = sum(1 for v in self.violations if v.severity == 'critical')
        warning = sum(1 for v in self.violations if v.severity == 'warning')
        info = sum(1 for v in self.violations if v.severity == 'info')
        
        score = 100
        score -= critical * 20
        score -= warning * 5
        score -= info * 1
        score = max(0, score)
        
        compliant = critical == 0 and warning == 0
        
        return {
            'compliant': compliant,
            'score': score,
            'violations': [
                {
                    'rule': v.rule,
                    'category': v.category,
                    'severity': v.severity,
                    'value': v.value,
                    'message': v.message
                }
                for v in self.violations
            ],
            'summary': {
                'critical': critical,
                'warning': warning,
                'info': info,
                'total': len(self.violations)
            }
        }


def validate_email_branding(html: str) -> Dict[str, Any]:
    """
    Convenience function to validate email HTML.
    
    Args:
        html: HTML string to validate
        
    Returns:
        Validation report dictionary
    """
    validator = BrandValidator()
    return validator.validate(html)
