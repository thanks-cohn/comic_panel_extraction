~~~

                            ██████╗  ██████╗ ███╗   ███╗ ██╗  ██████╗ █████╗ 
                           ██╔════╝ ██╔═══██╗████╗ ████║ ██║ ██╔════╝██╔══██╗
                           ██║      ██║   ██║██╔████╔██║ ██║ ██║     ███████║
                           ██║      ██║   ██║██║╚██╔╝██║ ██║ ██║     ██╔══██║
                           ╚██████╗ ╚██████╔╝██║ ╚═╝ ██║ ██║ ╚██████╗██║  ██║
                             ╚═════╝  ╚═════╝ ╚═╝    ╚═╝  ╚═╝  ╚═════╝╚═╝ ╚═╝

~~~

# COMICA — Comic Panel Extraction & Layout Engine

## PDF / IMAGE → STRUCTURED COMIC LAYOUT (SVG + JSON)

Comic panel extraction tool for PDF and images.  
COMICA performs comic segmentation, panel detection, and layout reconstruction, outputting structured SVG and JSON for datasets, analysis, and tooling.

Keywords: comic panel extraction, comic segmentation, panel detection, comic layout analysis, PDF comic parser, comic dataset generation

"Structure, not noise."

------------------------------------------------------------
 WHAT THIS DOES
------------------------------------------------------------

Comica takes a comic page and extracts its *layout*.

Not loosely.
Not visually.

Structurally.

It performs **comic panel extraction and segmentation**, identifying panels,
preserving their geometry, and rebuilding the page as a system of objects.

Each page becomes something you can:
  • inspect  
  • move  
  • reuse  
  • rebuild  

------------------------------------------------------------
 CORE OUTPUT
------------------------------------------------------------

For every page, Comica produces:

1. SVG (structured comic layout)
   - Panels as independent object groups  
   - Exact bounding regions preserved  
   - Page reconstructed as layered geometry  

2. Spatial JSON (source of truth)
   - Panel coordinates  
   - Page dimensions  
   - Object metadata  
   - Detection source + confidence  

3. Panel Crops (panel extraction assets)
   - Each panel saved as its own image  
   - Linked directly to its spatial definition  
   - Includes hashes + file metadata  

→ JSON defines the system  
→ SVG renders the system  

------------------------------------------------------------
 COMIC PANEL EXTRACTION & SEGMENTATION
------------------------------------------------------------

COMICA focuses on **panel detection and comic segmentation**.

• Strong panel extraction from PDF and images  
• Clean, consistent panel bounding boxes  
• Layout-aware segmentation  
• Tunable detection profiles  
• Adaptable across comic styles  

This is not simple image slicing.

This is **layout-aware comic panel extraction**.

------------------------------------------------------------
 CURRENT STATE
------------------------------------------------------------

✔ Panel detection: STRONG  
✔ Comic segmentation: RELIABLE  
✔ SVG reconstruction: STABLE  
✔ Spatial JSON: SOLID  

⚠ Caveats:

• Some layouts require tuning (profile / zoom)  
• Extremely unconventional pages may break assumptions  
• Detection is geometry-based, not semantic  

This is a **comic layout extraction engine**, not a full understanding system.

------------------------------------------------------------
 WHY THIS MATTERS
------------------------------------------------------------

Most comic tools flatten pages into images.

COMICA preserves:

  structure

Once comic layout is structured:

  → panels can be extracted cleanly  
  → layouts can be analyzed  
  → pages can be rebuilt  

------------------------------------------------------------
 APPLICATIONS
------------------------------------------------------------

• Comic panel extraction datasets  
• Comic segmentation pipelines  
• PDF comic parsing  
• Layout-aware comic editors  
• Comic dataset generation  
• Panel indexing and retrieval  
• Comic layout analysis  
• Foundations for multimodal systems  

------------------------------------------------------------
 EXAMPLE
------------------------------------------------------------

python comica_object_svg_miracle.py input.pdf -o out

→ Output:

out/
  ├── spatial_json/
  │     page_0001.comica.page.json
  ├── svg/
  │     page_0001.comica.svg
  ├── panels/
  │     page_0001_panel_01.png
  └── pages/
        page_0001.png

------------------------------------------------------------
 PHILOSOPHY
------------------------------------------------------------

A comic page is not just an image.

It is a layout.

Comica captures the layout.

------------------------------------------------------------
 THE PROMISE
------------------------------------------------------------

Right now:
  → Reliable comic panel extraction  
  → Clean segmentation outputs  

Next:
  → More robust layout handling  
  → Expanded detection control  
  → Deeper structural modeling  

Long term:
  → A foundation for comic-aware systems  

------------------------------------------------------------
 POSSIBILITIES
------------------------------------------------------------

If you're working with:

  comic panel extraction  
  comic segmentation  
  comic datasets  
  comic layout systems  

this gives you something most tools don’t:

control over the layout itself.

------------------------------------------------------------
