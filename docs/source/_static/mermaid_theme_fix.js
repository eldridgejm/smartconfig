// Fix for Mermaid theme switching with Alpine.js-based themes
//
// WHY THIS IS NEEDED:
// sphinxcontrib-mermaid v1.2.3 doesn't include any automatic theme detection.
// Diagrams are rendered once with the default (light) theme and don't update
// when the user toggles between light and dark mode. This fix adds dynamic
// theme switching by detecting changes to the page theme and re-rendering
// diagrams accordingly.
//
// HOW IT WORKS:
// 1. Store the original diagram code before mermaid processes it
// 2. Render diagrams with the correct theme on initial page load
// 3. Use a MutationObserver to detect when the 'dark' class changes on <html>
// 4. When a theme change is detected, reinitialize mermaid with the new theme
//    and re-render all diagrams from their original source code

import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11.12.1/dist/mermaid.esm.min.mjs";

const isDark = () => document.documentElement.classList.contains('dark');

// Store original diagram code
document.querySelectorAll('.mermaid').forEach(el => {
    el.setAttribute('data-original-code', el.textContent);
});

const renderMermaid = async () => {
    try {
        await mermaid.initialize({
            startOnLoad: false,
            darkMode: isDark(),
            theme: isDark() ? 'dark' : 'default'
        });

        document.querySelectorAll('.mermaid').forEach(el => {
            el.removeAttribute('data-processed');
            el.textContent = el.getAttribute('data-original-code');
        });

        await mermaid.run();
    } catch (error) {
        // Ignore rendering errors
    }
};

// Render with correct theme on initial load
renderMermaid();

// Watch for theme changes and re-render
let lastDarkMode = isDark();
new MutationObserver(() => {
    if (isDark() !== lastDarkMode) {
        lastDarkMode = isDark();
        renderMermaid();
    }
}).observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
