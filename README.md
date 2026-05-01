~~~

                            ██████╗  ██████╗ ███╗   ███╗ ██╗  ██████╗ █████╗ 
                           ██╔════╝ ██╔═══██╗████╗ ████║ ██║ ██╔════╝██╔══██╗
                           ██║      ██║   ██║██╔████╔██║ ██║ ██║     ███████║
                           ██║      ██║   ██║██║╚██╔╝██║ ██║ ██║     ██╔══██║
                           ╚██████╗ ╚██████╔╝██║ ╚═╝ ██║ ██║ ╚██████╗██║  ██║
                             ╚═════╝  ╚═════╝ ╚═╝    ╚═╝  ╚═╝  ╚═════╝╚═╝ ╚═╝

~~~

# COMICA — OBJECT SVG ENGINE


# PDF / IMAGE → STRUCTURED COMIC LAYOUT




"Structure, not noise."

------------------------------------------------------------
 WHAT THIS DOES
------------------------------------------------------------

Comica takes a comic page and extracts its *layout*.

Not loosely.
Not visually.

Structurally.

It identifies panels, preserves their geometry, and rebuilds the page
as a system of objects instead of a flat image.

Each page becomes something you can:
  • inspect
  • move
  • reuse
  • rebuild

------------------------------------------------------------
 CORE OUTPUT
------------------------------------------------------------

For every page, Comica produces:

1. SVG (the visible structure)
   - Panels as independent object groups
   - Exact bounding regions preserved
   - Page reconstructed as layered geometry

2. Spatial JSON (the source of truth)
   - Panel coordinates
   - Page dimensions
   - Object metadata
   - Detection source + confidence

3. Panel Crops (asset layer)
   - Each panel saved as its own image
   - Linked directly to its spatial definition
   - Includes hashes + file metadata

→ JSON defines the system  
→ SVG renders the system  

------------------------------------------------------------
 WHAT IT DOES WELL
------------------------------------------------------------

• Strong panel detection  
• Clean, consistent panel bounding regions  
• Preserves page layout faithfully  
• Produces reusable structured outputs  
• Rebuilds SVGs directly from JSON  

The panel segmentation is the core strength:

  → stable  
  → tunable (profiles + thresholds)  
  → adaptable to different comic styles  

------------------------------------------------------------
 CURRENT STATE
------------------------------------------------------------

✔ Panel detection: STRONG  
✔ SVG reconstruction: STABLE  
✔ Spatial JSON: SOLID  

⚠ Caveats:

• Some layouts require tuning (profile / zoom)  
• Extremely unconventional pages may break assumptions  
• Detection is geometry-based, not semantic  

This is a **layout extraction engine**, not a full understanding system.

------------------------------------------------------------
 WHY THIS MATTERS
------------------------------------------------------------

Most tools flatten comics into images.

Comica preserves:

  structure

And once structure exists:

  → it can be edited  
  → it can be analyzed  
  → it can be rebuilt  

------------------------------------------------------------
 APPLICATIONS
------------------------------------------------------------

• Panel-level dataset creation  
• Layout-aware editing tools  
• Comic composition analysis  
• Panel indexing and retrieval  
• Asset extraction pipelines  
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

A comic page is not an image.

It is an arrangement.

Comica captures the arrangement.

------------------------------------------------------------
 THE PROMISE
------------------------------------------------------------

Right now:
  → Reliable panel extraction  
  → Clean structural outputs  

Next:
  → More robust layout handling  
  → Expanded control + tuning  
  → Deeper structural modeling  

Long term:
  → A foundation for comic-aware systems  

------------------------------------------------------------
 POSSIBILITES
------------------------------------------------------------

If you're working with comics as data, structure, or systems—

this gives you something most tools don’t:

control over the layout itself.

------------------------------------------------------------
