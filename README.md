---
title: Genetic Algorithm Timetable Generator
emoji: 🗓️
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
app_port: 7860
---

# Timetable Generator

This repository contains a Python-based timetable generation system for educational institutes. It leverages a **Genetic Algorithm** to produce optimized schedules without resource conflicts. 

The system features both a **desktop GUI** built with `tkinter` and a modern **web-based UI** built with `Gradio`, backed by a `FastAPI` server. It is fully containerized and deployable to cloud platforms like Hugging Face Spaces.

## 🚀 Features

- **Genetic Algorithm Optimization:** Uses evolutionary techniques to resolve complex scheduling constraints.
- **Web UI & API (Gradio + FastAPI):** Interactive web interface for managing courses, tracking progress, and downloading schedules.
- **Desktop GUI (Tkinter):** Rich desktop application with frame-based navigation, real-time console redirection, and custom styling.
- **Database Integration:** SQLite backend for managing courses, teachers, branches, and class frequency requirements.
- **Data Visualization & Export:** View generated timetables in a grid format and export directly to Excel with professional formatting.

## 🧬 Algorithm & Core Data Structures

The application relies on highly optimized data structures to evaluate fitness and resolve scheduling conflicts rapidly.

### Advanced Conflict Detection
- **Sets for O(1) Lookups:** `Set` data structures are extensively used to track unique elements and detect double-booking conflicts (teachers, rooms, branches) instantly. This $O(1)$ lookup time is critical for the fitness function, which must evaluate thousands of potential timetables during generation.

### Constraint Resolution Engine
- **Max Heap Implementation:** A priority queue (implemented via Python's `heapq`) is used to optimize constraint resolution (`fix_overassigned_classes` and `fix_class_assignments`). By processing the most severe constraint violations first, the algorithm makes impactful changes early, leading to much faster convergence.
  - *Theoretical impact:* Reduces constraint resolution time complexity from $O(m \times n)$ to $O(n \log n + m \log n)$ for $n$ classes and $m$ constraints.

### Genetic Operators
- **Tournament Selection:** Efficient random sampling to select optimal parent schedules.
- **Crossover & Mutation:** Schedule slots are intelligently combined and mutated to explore the solution space effectively while maintaining valid `ClassSlot` objects.

## 🖥️ Desktop & Web Interfaces

### Web Application (Cloud Ready)
The project includes a `frontend.py` Gradio application and an `app.py` FastAPI server. These allow you to generate and view schedules from any browser, making it ideal for cloud deployment.

### Tkinter Desktop GUI (`modern_timetable_gui.py`)
The desktop interface provides a native experience featuring:
- **Visual Design:** A modern, card-based layout with consistent typography and color-coded feedback.
- **Console Output Redirection:** System logs and algorithm progress are streamed directly to a scrollable widget within the application using a custom `StdoutRedirector`.
- **Workflow Optimization:** Dedicated notebook tabs guide users logically through database setup, relationship configuration, class requirement specification, and timetable generation.

## 🐳 Docker Support & Deployment

A `Dockerfile` is provided for fully containerized execution. The setup uses a shell script (`run.sh`) to concurrently launch the FastAPI backend internally (port 8000) and expose the Gradio frontend externally (port 7860).

### Building the Image
```bash
docker build -t timetable-generator:latest .
```

### Running the Container
```bash
docker run --rm -it -p 7860:7860 -v "$PWD":/app timetable-generator:latest
```
- The `-v "$PWD":/app` flag mounts the current directory so that the SQLite database (`timetable.db`) persists on your host machine.
- Access the web interface at `http://localhost:7860`.

## 📦 Requirements

All external dependencies are listed in `requirements.txt`:
- `fastapi` & `uvicorn` (Backend API)
- `gradio` (Web Interface)
- `requests` (API Communication)
- `pandas` & `openpyxl` (Data Handling & Excel Export)
- `tabulate` (CLI Formatting)

All other modules rely solely on the Python standard library.
