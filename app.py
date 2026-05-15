from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import sqlite3
import os
from simplified_genetic_algorithm import genetic_algorithm
from db_operations import initialize_database, fetch_data_from_db, insert_timetable_into_db

app = FastAPI(title="Timetable Generator API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    if not os.path.exists("timetable.db"):
        print("Initializing database...")
        initialize_database()

@app.get("/")
async def root():
    return {"message": "Welcome to the Timetable Generator API", "status": "running"}

@app.post("/generate")
async def generate_timetable(generations: int = 100):
    try:
        # Fetch branches
        with sqlite3.connect("timetable.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT branch_name FROM branches")
            branches = [branch[0] for branch in cursor.fetchall()]

        if not branches:
            raise HTTPException(status_code=400, detail="No branches found in database")

        # Run genetic algorithm
        result = genetic_algorithm(branches, generations=generations)
        
        if result:
            schedule, professor_schedules = result
            # Save to DB
            insert_timetable_into_db(schedule)
            
            # Format output for JSON
            formatted_schedule = []
            for day in range(len(schedule)):
                for slot in range(len(schedule[day])):
                    slot_data = schedule[day][slot]
                    if slot_data:
                        if isinstance(slot_data, list):
                            for class_data in slot_data:
                                formatted_schedule.append({
                                    "day": day,
                                    "slot": slot,
                                    "course_code": class_data.course_code,
                                    "course_name": class_data.course_name,
                                    "teacher": class_data.teacher,
                                    "room": class_data.room,
                                    "branch": class_data.branch
                                })
                        else:
                            formatted_schedule.append({
                                "day": day,
                                "slot": slot,
                                "course_code": slot_data.course_code,
                                "course_name": slot_data.course_name,
                                "teacher": slot_data.teacher,
                                "room": slot_data.room,
                                "branch": slot_data.branch
                            })
            
            return {
                "status": "success",
                "message": "Timetable generated successfully",
                "data": formatted_schedule
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to generate a valid timetable")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/timetable")
async def get_timetable():
    try:
        with sqlite3.connect("timetable.db") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM timetable")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/initialize")
async def init_db():
    try:
        initialize_database()
        return {"status": "success", "message": "Database initialized with sample data"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats():
    try:
        with sqlite3.connect("timetable.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM branches")
            branches = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM courses")
            courses = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM teachers")
            teachers = cursor.fetchone()[0]
            return {
                "branches": branches,
                "courses": courses,
                "teachers": teachers
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/courses")
async def add_new_course(course_code: str, course_name: str, branch_name: str):
    try:
        from db_operations import add_course
        success = add_course(course_code, course_name, branch_name)
        if success:
            return {"status": "success", "message": f"Course {course_code} added"}
        else:
            raise HTTPException(status_code=400, detail="Failed to add course")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/courses/{course_code}")
async def remove_course(course_code: str):
    try:
        from db_operations import delete_course
        success = delete_course(course_code)
        if success:
            return {"status": "success", "message": f"Course {course_code} deleted"}
        else:
            raise HTTPException(status_code=400, detail="Failed to delete course")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/branches")
async def list_branches():
    try:
        with sqlite3.connect("timetable.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT branch_name FROM branches")
            return [r[0] for r in cursor.fetchall()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
