# PPTX Reference Templates

The large `.pptx` reference template files are **not stored in git** (they are 21MB+ each).

## What goes here (in git)

- `template_manifest.json` — the extracted slide pattern library (JSON, small, versioned in git)

## What stays local / in secure storage

- `book_schemas_janvier_2023_reference.pptx` — slide pattern library (~21MB)
- `jbf_ge_im_draft_reference.pptx` — IM narrative reference (~26MB)

## How to use

1. Copy your reference `.pptx` files into this folder on your local machine.
2. They will be picked up by `template_service.py` for deck planning.
3. The `template_manifest.json` is what Claude uses to select slide patterns —
   it was generated from the `.pptx` files by `scripts/inspect_ppt_templates.py`.

## Regenerating the manifest

If you add new reference templates:

```bash
python scripts/inspect_ppt_templates.py
```

This reads all `.pptx` files in this folder and writes a new `template_manifest.json`.

## Production / Railway

For Railway deployments, the app functions without the `.pptx` files present.
The deck generation uses the `template_manifest.json` for slide planning and
generates slides programmatically (not by copying from the reference files).

To provide reference templates in production, either:
- Include them in a Railway volume mounted at `/app/templates/pptx/`
- Or use an S3 bucket and add a startup fetch step
