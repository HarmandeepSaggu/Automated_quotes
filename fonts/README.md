# Fonts

For the intended editorial look, place licensed font files in this directory using one of these names:

- `CormorantGaramond-Italic.ttf`
- `PlayfairDisplay-Italic.ttf`
- `LibreBaskerville-Italic.ttf`

The renderer tries these files in order, then checks common system font locations and finally falls back to Pillow's default font. The fallback keeps the application runnable, but a production deployment should install one of the preferred fonts and verify the generated image before publishing.

Font files are intentionally not bundled because font licenses differ by distribution.
