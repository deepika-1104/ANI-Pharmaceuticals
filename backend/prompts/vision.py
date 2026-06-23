"""
Vision LLM prompts for image extraction.

VISION_PROMPT_DEFAULT  — general images (charts, tables, diagrams, photos).
VISION_PROMPT_MEDICAL  — retry prompt for clinical images that trigger safety filters.
"""

VISION_PROMPT_DEFAULT = """\
Analyze this image thoroughly and extract all content:

1. TEXT: Transcribe ALL visible text exactly as written — labels, titles, captions, \
annotations, legends, axis labels, values.
2. CHARTS/GRAPHS: State the chart type, axis titles and ranges, every data series \
name and its values, and any visible trend.
3. TABLES: Reproduce all rows and columns as structured text with headers.
4. DIAGRAMS/FLOWCHARTS: Describe all nodes, connections, arrows, and labels in reading order.
5. PHOTOS/GENERAL: Describe what is shown and transcribe all readable text.

Output the full extracted content clearly and completely. \
This content will be used to answer user questions about this image.\
"""

VISION_PROMPT_MEDICAL = """\
This is a medical or clinical image submitted for educational and informational indexing.

Analyze the image thoroughly and extract all content:

1. TEXT: Transcribe ALL visible text exactly — labels, annotations, measurements, \
identifiers, scale bars.
2. ANATOMICAL/CLINICAL: Describe structures, regions, findings, or pathology visible \
in the image using standard medical terminology.
3. CHARTS/GRAPHS: State chart type, axes, all data points and values.
4. TABLES: Reproduce all rows and columns with headers.
5. DIAGRAMS: Describe all labeled components and their relationships.

Output the full extracted content clearly and completely. \
This content will be used for clinical knowledge retrieval.\
"""
