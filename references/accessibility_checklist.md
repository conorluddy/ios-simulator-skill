# iOS Accessibility Checklist

## Critical Rules (Must Fix)

### 1. Interactive elements need labels
**Check:** `accessibilityLabel != nil`
**Fix:** Add descriptive label

### 2. Buttons need text
**Check:** `label || value != ""`
**Fix:** Set button title or accessibilityLabel

### 3. Images need descriptions
**Check:** `isImage && accessibilityLabel`
**Fix:** Add alt text via accessibilityLabel

## Warnings (Should Fix)

### 4. Complex controls need hints
**Check:** `accessibilityHint for custom controls`
**Fix:** Explain what happens on activation

### 5. Grouped elements need containers
**Check:** `isAccessibilityElement on containers`
**Fix:** Group related elements

### 6. Text fields need placeholders
**Check:** `placeholder || accessibilityLabel`
**Fix:** Add placeholder text

## Info (Nice to Have)

### 7. Automation identifiers
**Check:** `accessibilityIdentifier != nil`
**Fix:** Add for UI testing

### 8. Trait specification
**Check:** `accessibilityTraits set correctly`
**Fix:** Use .button, .link, .header appropriately

### 9. Frame size adequate
**Check:** `frame.width >= 44 && frame.height >= 44`
**Fix:** Minimum touch target 44x44pt

## Quick Audit Command

```bash
python scripts/accessibility_audit.py
```

## iOS Code Fixes

```swift
// Label
button.accessibilityLabel = "Submit form"

// Hint
slider.accessibilityHint = "Adjusts volume"

// Identifier
view.accessibilityIdentifier = "login-button"

// Traits
label.accessibilityTraits = .header
```