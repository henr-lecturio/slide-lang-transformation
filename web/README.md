# Web UI

Start local UI server:

```bash
source .venv/bin/activate
python web/server.py
```

Open:

```text
http://127.0.0.1:8000
```

Functions:
- Edit/save ROI and keyframe-heuristic values in `config/slitranet.env`
- Regenerate and view `output/roi_tuning/roi_overlay.png`
- Start new SliTraNet runs
- Track run status and logs
- Browse run images and CSV under `output/runs/<timestamp>/...`
