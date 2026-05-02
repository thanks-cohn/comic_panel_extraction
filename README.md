~~~

                            ██████╗  ██████╗ ███╗   ███╗ ██╗  ██████╗
                           ██╔════╝ ██╔═══██╗████╗ ████║ ██║ ██╔════╝
                           ██║      ██║   ██║██╔████╔██║ ██║ ██║     
                           ██║      ██║   ██║██║╚██╔╝██║ ██║ ██║     
                           ╚██████╗ ╚██████╔╝██║ ╚═╝ ██║ ██║ ╚██████╗  
                             ╚═════╝  ╚═════╝ ╚═╝    ╚═╝  ╚═╝  ╚═════
                                            ██████╗ 
                                            ╚════██╗
                                             █████╔╝
                                            ██╔═══╝ 
                                            ███████╗
                                            ╚══════╝
                                ██████╗  █████╗ ███╗   ██╗███████╗██╗     
                                ██╔══██╗██╔══██╗████╗  ██║██╔════╝██║     
                                ██████╔╝███████║██╔██╗ ██║█████╗  ██║     
                                ██╔═══╝ ██╔══██║██║╚██╗██║██╔══╝  ██║     
                                ██║     ██║  ██║██║ ╚████║███████╗███████╗
                                ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚══════╝
                                                                  
~~~


#                comic2panel 
## Panel Extraction & Structural Reconstruction Engine

PDF / IMAGE → PANELS + TEXT + STRUCTURE (SVG + JSON)

"Pages are not images. They are systems."

------------------------------------------------------------
 WHAT THIS IS
------------------------------------------------------------

comic2panel is a **layout extraction engine** for comics.

It does not treat pages as flat images.

It treats them as:

  → panels  
  → gutters  
  → text lines  
  → spatial relationships  

All reconstructed into a structured, editable format.

------------------------------------------------------------
 CORE CAPABILITIES
------------------------------------------------------------

comic2panel takes a PDF or image and produces:

1. PANEL REGIONS
   - Detected using contours + gutter inference
   - Clean bounding boxes
   - Reading order preserved
   - Each panel becomes an object

2. TEXT (LINE-BY-LINE)
   - Extracted from PDF-native text when available
   - Falls back to OCR (PaddleOCR) when needed
   - Every line becomes its own object
   - Linked to its panel

3. GUTTERS
   - Detected as structural separators
   - Preserved as objects (not ignored)
   - Used to improve layout inference

4. SVG OUTPUT
   - Fully reconstructed page
   - Panels as grouped objects
   - Text as independent elements
   - Editable, inspectable, reusable

5. SPATIAL JSON
   - Source of truth
   - Stores geometry, relationships, metadata
   - SVG is rebuilt from this — not memory

6. PANEL CROPS
   - Each panel saved as its own image
   - Linked back to spatial definition

→ JSON defines the system  
→ SVG renders the system  

------------------------------------------------------------
 WHAT MAKES IT DIFFERENT
------------------------------------------------------------

Most tools:
  → slice images  
  → maybe detect panels  
  → lose structure  

comic2panel:
  → reconstructs the page as a **system of objects**

It preserves:

  structure  
  relationships  
  geometry  
  hierarchy  

Not just pixels.

------------------------------------------------------------
 TEXT EXTRACTION (IMPORTANT)
------------------------------------------------------------

This tool actually handles text *properly*.

• PDF-native extraction (clean, accurate when available)  
• OCR fallback using PaddleOCR  
• Line-by-line segmentation  
• Each line becomes an SVG object  

Not blobs.  
Not paragraphs.  
Not guesses.

Actual usable text objects.

------------------------------------------------------------
 PANEL DETECTION
------------------------------------------------------------

Panel detection is:

✔ Strong  
✔ Tunable  
✔ Multi-strategy  

It combines:

• Contour detection  
• Gutter inference  
• Hybrid merging  
• Fallback recovery (whole-page rescue if needed)  

Profiles:

  strict   → fewer, cleaner panels  
  balanced → default (good general use)  
  loose    → more aggressive detection  
  recall   → maximum capture  
  comic    → tuned for comic layouts  

------------------------------------------------------------
 OUTPUT STRUCTURE
------------------------------------------------------------

Example:

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
 USAGE
------------------------------------------------------------

Basic:

  python comic2panel.py input.pdf -o out

More control:

  python comic2panel.py input.pdf -o out --panel-profile balanced
  python comic2panel.py input.pdf -o out --panel-source hybrid
  python comic2panel.py input.pdf -o out --ocr paddle
  python comic2panel.py input.pdf -o out --prefer-ocr

Image folders:

  python comic2panel.py ./images -o out --ocr paddle

Manual panel override:

  python comic2panel.py input.pdf -o out --manual-panels panels.json

------------------------------------------------------------
 CURRENT STATE
------------------------------------------------------------

✔ Panel detection: solid  
✔ Text extraction: reliable (PDF + OCR fallback)  
✔ SVG reconstruction: stable  
✔ JSON structure: consistent  

⚠ Limitations:

• Unconventional layouts may need tuning  
• OCR quality depends on input quality  
• Detection is geometric, not semantic  
• Not “comic understanding” — yet  

------------------------------------------------------------
 WHY THIS MATTERS
------------------------------------------------------------

Once a comic page becomes structured:

  → panels can be indexed  
  → text becomes searchable  
  → layouts can be analyzed  
  → datasets can be built  
  → pages can be reconstructed  

This is not just extraction.

It’s **conversion into a usable system**.

------------------------------------------------------------
 APPLICATIONS
------------------------------------------------------------

• Comic dataset generation  
• Panel-level indexing  
• Searchable comic archives  
• Multimodal training data  
• Layout-aware editors  
• Comic analysis pipelines  
• SVG-based tooling  

------------------------------------------------------------
 THE REAL VALUE
------------------------------------------------------------

This gives you something most tools don’t:

control over the page as a structure.

Not just:

  what it looks like

But:

  how it is built

------------------------------------------------------------
 PHILOSOPHY
------------------------------------------------------------

A comic page is not an image.

It is a composition of intent:

  frames  
  spacing  
  text  
  flow  

comic2panel extracts that intent  
and turns it into something you can work with.

------------------------------------------------------------
 THE PROMISE
------------------------------------------------------------

Right now:

  → Reliable panel extraction  
  → Real text objects  
  → Structured outputs  

Next:

  → Better layout inference  
  → Stronger text-panel relationships  
  → Dataset-scale processing  

Long term:

  → Foundations for comic-aware systems  

------------------------------------------------------------
