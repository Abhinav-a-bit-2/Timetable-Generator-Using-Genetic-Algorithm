# Timetable Generator

This repository contains a Python-based timetable generation system for educational institutes. It includes:

- command-line interface (`main.py`)
- graphical user interface (`modern_timetable_gui.py`) using `tkinter`
- genetic algorithm implementation (`simplified_genetic_algorithm.py`)
- SQLite database operations (`db_operations.py`)
- utility scripts for course management (`course_management.py`)

## Docker Support 🐳

A `Dockerfile` is provided to make the project easy to run on any machine and to prepare it for publishing on GitHub.

### Building the Image

```bash
# from the repository root
docker build -t timetable-generator:latest .
```

### Running the Container

By default the container starts the CLI:

```bash
docker run --rm -it -v "$PWD":/app timetable-generator:latest
```

- The `-v "$PWD":/app` flag mounts the current directory so that any generated `timetable.db` stays on your host.

> You can use a different path by setting the `TIMETABLE_DB` environment variable when starting the container. The code will respect this value.
- If you want to access the GUI, you can run with X forwarding (Linux/Mac) or use a VNC/X server; additional setup is required.

### Custom Entry Points

You can override the command when you start the container:

```bash
# launch GUI (requires display setup)
docker run --rm -it -v "$PWD":/app timetable-generator:latest python modern_timetable_gui.py
```

### Database Initialization

The image initializes a clean `timetable.db` during build. If you mount a volume with an existing database, the container will use that file instead.

## Preparing for GitHub

To make the repository ready for GitHub:

1. Ensure this `README.md` is present.
2. Add a `.gitignore` (see below) and commit the project files.
3. Push the repository to your GitHub account.
4. Users can clone the repo and run `docker build`/`docker run` as shown above.

### .gitignore (suggested)

```
__pycache__/
*.pyc
*.db
.env
.venv/
```

## Requirements

The only external Python dependency is:

- `tabulate` (used for pretty-printing tables in the console)

All other modules are part of the Python standard library.

## License

Place your preferred open-source license here.
