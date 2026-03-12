import sqlite3
import random

DAYS = 5  # Monday to Friday
SLOTS_PER_DAY = 9  # 9 slots per day
DB_PATH = "timetable.db"

def get_course_classes():
    """Get the number of classes per course from the database."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cc.course_code, cc.num_classes, c.course_name, c.branch_name
            FROM course_classes cc
            JOIN courses c ON cc.course_code = c.course_code
            ORDER BY c.branch_name, c.course_code
        """)
        return cursor.fetchall()

def set_course_classes(course_code, num_classes):
    """Set the number of classes per course in the database."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE course_classes SET num_classes = ? WHERE course_code = ?",
                (num_classes, course_code)
            )
            conn.commit()
            return True
        except sqlite3.Error as e:
            conn.rollback()
            print(f" Database error: {e}")
            return False

def fetch_data_from_db():
    """Fetch courses, teachers, rooms, and branch mappings from the database."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Fetch all required data in one function
        cursor.execute("SELECT course_code, branch_name, course_name FROM courses")
        courses = cursor.fetchall()

        cursor.execute("""
            SELECT t.teacher_name, c.course_code, t.branch_name
            FROM branch_teacher_courses btc
            JOIN teachers t ON btc.teacher_id = t.teacher_id
            JOIN courses c ON btc.course_code = c.course_code
            WHERE t.branch_name = c.branch_name
        """)
        teachers = cursor.fetchall()

        cursor.execute("SELECT room_name FROM rooms")
        rooms = [room[0] for room in cursor.fetchall()]

        # Print debug information
        print(f"Fetched {len(courses)} courses, {len(teachers)} teacher-course-branch mappings, and {len(rooms)} rooms")

        # Check if we have valid data
        if not courses or not teachers or not rooms:
            print(" WARNING: Missing data in the database!")
            if not courses: print("  - No courses found")
            if not teachers: print("  - No teacher-course-branch mappings found")
            if not rooms: print("  - No rooms found")

    return courses, teachers, rooms

def add_professor(teacher_name, branch_name):
    """Add a new professor to the database with branch assignment."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        try:
            # Check if branch exists
            cursor.execute("SELECT branch_id FROM branches WHERE branch_name = ?", (branch_name,))
            if not cursor.fetchone():
                print(f" Branch '{branch_name}' does not exist. Please add it first.")
                return False

            cursor.execute(
                "INSERT INTO teachers (teacher_name, branch_name) VALUES (?, ?)",
                (teacher_name, branch_name),
            )
            conn.commit()
            print(f" Professor {teacher_name} added successfully to branch {branch_name}")
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

def get_all_professors():
    """Get all professors from the database."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT teacher_id, teacher_name, branch_name
            FROM teachers
            ORDER BY branch_name, teacher_name
        """)
        return cursor.fetchall()

def get_professor_courses(teacher_id):
    """Get all courses taught by a professor."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT btc.course_code, c.course_name, c.branch_name
            FROM branch_teacher_courses btc
            JOIN courses c ON btc.course_code = c.course_code
            WHERE btc.teacher_id = ?
            ORDER BY c.branch_name, c.course_name
        """, (teacher_id,))
        return cursor.fetchall()

def get_available_courses_for_professor(teacher_id):
    """Get all courses available for a professor to teach based on their branch."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # Get professor's branch and available courses in one transaction
        cursor.execute("SELECT branch_name FROM teachers WHERE teacher_id = ?", (teacher_id,))
        branch = cursor.fetchone()

        if not branch:
            return []

        cursor.execute("""
            SELECT c.course_code, c.course_name
            FROM courses c
            WHERE c.branch_name = ?
            AND c.course_code NOT IN (
                SELECT btc.course_code
                FROM branch_teacher_courses btc
                WHERE btc.teacher_id = ?
            )
            ORDER BY c.course_name
        """, (branch[0], teacher_id))
        return cursor.fetchall()

def add_course_to_professor(teacher_id, course_code):
    """Assign a course to a professor."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        try:
            # Validate professor and course in the same branch
            cursor.execute("SELECT branch_name FROM teachers WHERE teacher_id = ?", (teacher_id,))
            prof_result = cursor.fetchone()
            if not prof_result:
                print(f" Professor with ID {teacher_id} not found.")
                return False
            prof_branch = prof_result[0]

            cursor.execute("SELECT branch_name FROM courses WHERE course_code = ?", (course_code,))
            course_result = cursor.fetchone()
            if not course_result:
                print(f" Course with code {course_code} not found.")
                return False
            course_branch = course_result[0]

            if prof_branch != course_branch:
                print(f" Professor's branch ({prof_branch}) does not match course's branch ({course_branch}).")
                return False

            # Check for existing mapping
            cursor.execute(
                "SELECT 1 FROM branch_teacher_courses WHERE teacher_id = ? AND course_code = ?",
                (teacher_id, course_code)
            )
            if cursor.fetchone():
                print(f" Professor already teaches this course.")
                return False

            # Add the mapping
            cursor.execute(
                "INSERT INTO branch_teacher_courses (teacher_id, course_code) VALUES (?, ?)",
                (teacher_id, course_code)
            )
            conn.commit()
            print(f" Course {course_code} assigned to professor successfully.")
            return True
        except sqlite3.Error as e:
            conn.rollback()
            print(f"Database error: {e}")
            return False

def remove_course_from_professor(teacher_id, course_code):
    """Remove a course assignment from a professor."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        try:
            # Check if mapping exists and delete in one transaction
            cursor.execute(
                "SELECT 1 FROM branch_teacher_courses WHERE teacher_id = ? AND course_code = ?",
                (teacher_id, course_code)
            )
            if not cursor.fetchone():
                print(f" Professor does not teach this course.")
                return False

            cursor.execute(
                "DELETE FROM branch_teacher_courses WHERE teacher_id = ? AND course_code = ?",
                (teacher_id, course_code)
            )
            conn.commit()
            print(f" Course {course_code} removed from professor successfully.")
            return True
        except sqlite3.Error as e:
            conn.rollback()
            print(f"Database error: {e}")
            return False

def add_course(course_code, course_name, branch_name):
    """Add a new course to the database."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO courses (course_code, course_name, branch_name) VALUES (?, ?, ?)",
                (course_code, course_name, branch_name),
            )
            # Also add default entry in course_classes
            cursor.execute(
                "INSERT INTO course_classes (course_code, num_classes) VALUES (?, ?)",
                (course_code, 2)  # Default to 2 classes per week
            )
            conn.commit()
            print(f" Course '{course_code}' added successfully to branch '{branch_name}'!")
            return True
        except sqlite3.Error as e:
            conn.rollback()
            print(f"Database error: {e}")
            return False

def check_teacher_by_course_code(course_code):
    """Check if any teacher is associated with the given course code."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        try:
            # Get course info and teachers in one transaction
            cursor.execute("SELECT branch_name FROM courses WHERE course_code = ?", (course_code,))
            branch_result = cursor.fetchone()

            if not branch_result:
                print(f"❌ Course code '{course_code}' does not exist.")
                return False

            branch_name = branch_result[0]

            cursor.execute("""
                SELECT t.teacher_name
                FROM branch_teacher_courses btc
                JOIN teachers t ON btc.teacher_id = t.teacher_id
                WHERE btc.course_code = ? AND t.branch_name = ?
            """, (course_code, branch_name))

            results = cursor.fetchall()

            if results:
                print(f" Teachers associated with course '{course_code}' (Branch: {branch_name}):")
                for row in results:
                    print(f"- {row[0]}")
                return True
            else:
                print(f" No teachers found for course '{course_code}' in branch {branch_name}.")
                return False

        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

def fetch_branch_teacher_courses(branch_id):
    """Fetch teachers and courses for a specific branch."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.teacher_name, c.course_code, c.course_name
            FROM branch_teacher_courses btc
            JOIN teachers t ON btc.teacher_id = t.teacher_id
            JOIN courses c ON btc.course_code = c.course_code
            WHERE btc.branch_id = ?
        """, (branch_id,))
        return cursor.fetchall()


def insert_timetable_into_db(schedule):
    """Insert the final timetable into the database."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        try:
            # Clear existing timetable data
            cursor.execute("DELETE FROM timetable")

            # SQL for inserting timetable entries
            insert_sql = """
                INSERT INTO timetable (course_code, course_name, teacher, room, branch, day, slot, class_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """

            for day in range(DAYS):
                for slot in range(SLOTS_PER_DAY):
                    # Skip empty slots
                    if schedule[day][slot] is None:
                        continue

                    # Process the slot data
                    slot_data = schedule[day][slot]

                    # Skip lunch slots
                    if (isinstance(slot_data, list) and slot_data and
                        hasattr(slot_data[0], 'course_code') and slot_data[0].course_code == "LUNCH"):
                        continue
                    elif (not isinstance(slot_data, list) and hasattr(slot_data, 'course_code') and
                          slot_data.course_code == "LUNCH"):
                        continue

                    # Handle list of classes in a slot
                    if isinstance(slot_data, list):
                        for class_index, class_data in enumerate(slot_data):
                            if class_data is None:
                                continue

                            # Extract data from class_data
                            if hasattr(class_data, 'to_tuple'):
                                data_tuple = class_data.to_tuple()
                                if len(data_tuple) >= 7:
                                    course_code, course_name, teacher, room, branch, d, s = data_tuple
                                    cursor.execute(insert_sql,
                                                  (course_code, course_name, teacher, room, branch, d, s, class_index))
                            elif isinstance(class_data, tuple) and len(class_data) >= 7:
                                course_code, course_name, teacher, room, branch, d, s = class_data
                                cursor.execute(insert_sql,
                                              (course_code, course_name, teacher, room, branch, d, s, class_index))

                    # Handle single class in a slot
                    elif hasattr(slot_data, 'to_tuple'):
                        data_tuple = slot_data.to_tuple()
                        if len(data_tuple) >= 7:
                            course_code, course_name, teacher, room, branch, d, s = data_tuple
                            cursor.execute(insert_sql,
                                          (course_code, course_name, teacher, room, branch, d, s, 0))

                    # Handle tuple case (backward compatibility)
                    elif isinstance(slot_data, tuple) and len(slot_data) >= 7:
                        course_code, course_name, teacher, room, branch, d, s = slot_data
                        cursor.execute(insert_sql,
                                      (course_code, course_name, teacher, room, branch, d, s, 0))

            conn.commit()
            print(" Timetable inserted successfully into the database!")
            return True
        except sqlite3.Error as e:
            conn.rollback()
            print(f" Database error: {e}")
            return False


def add_branch_teacher_course_mapping(branch_name, teacher_name, course_code):
    """Add a mapping between a branch, teacher, and course."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        try:
            # Validate branch, teacher, and course in one transaction
            cursor.execute("""
                SELECT b.branch_id, t.teacher_id, t.branch_name, c.branch_name
                FROM branches b
                LEFT JOIN teachers t ON t.teacher_name = ? AND t.branch_name = b.branch_name
                LEFT JOIN courses c ON c.course_code = ? AND c.branch_name = b.branch_name
                WHERE b.branch_name = ?
            """, (teacher_name, course_code, branch_name))

            result = cursor.fetchone()
            if not result:
                print(f" Branch '{branch_name}' does not exist.")
                return False

            branch_id, teacher_id, teacher_branch, course_branch = result

            # Validate teacher
            if not teacher_id:
                print(f" Teacher '{teacher_name}' does not exist or is not in branch '{branch_name}'.")
                return False

            # Validate course
            if not course_branch:
                print(f" Course '{course_code}' does not exist or is not in branch '{branch_name}'.")
                return False

            # Check if mapping already exists
            cursor.execute(
                "SELECT 1 FROM branch_teacher_courses WHERE branch_id = ? AND teacher_id = ? AND course_code = ?",
                (branch_id, teacher_id, course_code)
            )
            if cursor.fetchone():
                print(f" Mapping already exists for branch '{branch_name}', teacher '{teacher_name}', and course '{course_code}'.")
                return False

            # Add mapping
            cursor.execute(
                "INSERT INTO branch_teacher_courses (branch_id, teacher_id, course_code) VALUES (?, ?, ?)",
                (branch_id, teacher_id, course_code)
            )
            conn.commit()
            print(f" Added mapping: Branch '{branch_name}', Teacher '{teacher_name}', Course '{course_code}'")
            return True

        except sqlite3.Error as e:
            conn.rollback()
            print(f"Database error: {e}")
            return False


def add_branch(branch_name):
    """Add a new branch to the database."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        try:
            # Check if branch already exists and add in one transaction
            cursor.execute("SELECT branch_id FROM branches WHERE branch_name = ?", (branch_name,))
            if cursor.fetchone():
                print(f" Branch '{branch_name}' already exists.")
                return False

            cursor.execute("INSERT INTO branches (branch_name) VALUES (?)", (branch_name,))
            conn.commit()
            print(f" Added branch: {branch_name}")
            return True

        except sqlite3.Error as e:
            conn.rollback()
            print(f"Database error: {e}")
            return False

def delete_course(course_code):
    """Delete a course from the database with all related records."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        try:
            # Check if course exists
            cursor.execute("SELECT course_name, branch_name FROM courses WHERE course_code = ?", (course_code,))
            course_result = cursor.fetchone()
            if not course_result:
                print(f" Course '{course_code}' does not exist.")
                return False

            course_name, branch_name = course_result

            # Begin transaction
            conn.execute("BEGIN TRANSACTION")

            # Get all teacher mappings for this course
            cursor.execute("""
                SELECT btc.id, t.teacher_name
                FROM branch_teacher_courses btc
                JOIN teachers t ON btc.teacher_id = t.teacher_id
                WHERE btc.course_code = ?
            """, (course_code,))

            mappings = cursor.fetchall()
            mapping_count = len(mappings)

            # Delete all mappings
            if mapping_count > 0:
                cursor.execute("DELETE FROM branch_teacher_courses WHERE course_code = ?", (course_code,))
                print(f"  - Removed {mapping_count} teacher-course mappings:")
                for _, teacher_name in mappings:
                    print(f"    * {teacher_name}")

            # Delete from course_classes
            cursor.execute("DELETE FROM course_classes WHERE course_code = ?", (course_code,))

            # Delete from timetable
            cursor.execute("SELECT COUNT(*) FROM timetable WHERE course_code = ?", (course_code,))
            timetable_count = cursor.fetchone()[0]
            if timetable_count > 0:
                cursor.execute("DELETE FROM timetable WHERE course_code = ?", (course_code,))
                print(f"  - Removed {timetable_count} timetable entries for this course")

            # Finally delete the course
            cursor.execute("DELETE FROM courses WHERE course_code = ?", (course_code,))

            conn.commit()
            print(f" Successfully deleted course '{course_code}' ({course_name}) from branch '{branch_name}'")
            return True

        except sqlite3.Error as e:
            conn.rollback()
            print(f" Database error: {e}")
            return False

def delete_course_teacher_mapping(branch_name, teacher_name, course_code):
    """Delete a specific course-teacher mapping."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        try:
            # Get all required IDs in one query
            cursor.execute("""
                SELECT b.branch_id, t.teacher_id, btc.id
                FROM branches b
                JOIN teachers t ON t.branch_name = b.branch_name AND t.teacher_name = ?
                JOIN branch_teacher_courses btc ON btc.branch_id = b.branch_id
                    AND btc.teacher_id = t.teacher_id AND btc.course_code = ?
                WHERE b.branch_name = ?
            """, (teacher_name, course_code, branch_name))

            result = cursor.fetchone()
            if not result:
                # Check which part of the mapping doesn't exist
                cursor.execute("SELECT 1 FROM branches WHERE branch_name = ?", (branch_name,))
                if not cursor.fetchone():
                    print(f" Branch '{branch_name}' does not exist.")
                    return False

                cursor.execute("SELECT 1 FROM teachers WHERE teacher_name = ? AND branch_name = ?",
                              (teacher_name, branch_name))
                if not cursor.fetchone():
                    print(f" Teacher '{teacher_name}' does not exist in branch '{branch_name}'.")
                    return False

                cursor.execute("SELECT 1 FROM courses WHERE course_code = ?", (course_code,))
                if not cursor.fetchone():
                    print(f" Course '{course_code}' does not exist.")
                    return False

                print(f" No mapping exists for branch '{branch_name}', teacher '{teacher_name}', and course '{course_code}'.")
                return False

            branch_id, teacher_id, mapping_id = result

            # Begin transaction
            conn.execute("BEGIN TRANSACTION")

            # Check if this mapping is used in timetable
            cursor.execute("""
                SELECT COUNT(*) FROM timetable
                WHERE course_code = ? AND teacher = ? AND branch = ?
            """, (course_code, teacher_name, branch_name))

            timetable_count = cursor.fetchone()[0]
            if timetable_count > 0:
                print(f" Warning: This mapping is used in {timetable_count} timetable entries.")
                print("   These entries will remain but may cause issues in future timetable generation.")

            # Delete the mapping
            cursor.execute("DELETE FROM branch_teacher_courses WHERE id = ?", (mapping_id,))

            conn.commit()
            print(f" Successfully deleted mapping: Branch '{branch_name}', Teacher '{teacher_name}', Course '{course_code}'")
            return True

        except sqlite3.Error as e:
            conn.rollback()
            print(f" Database error: {e}")
            return False

def initialize_database():
    """Initialize the database with required tables and sample data."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Drop existing tables if they exist
        cursor.execute("DROP TABLE IF EXISTS timetable")
        cursor.execute("DROP TABLE IF EXISTS branch_teacher_courses")
        cursor.execute("DROP TABLE IF EXISTS teachers")
        cursor.execute("DROP TABLE IF EXISTS course_classes")
        cursor.execute("DROP TABLE IF EXISTS courses")
        cursor.execute("DROP TABLE IF EXISTS rooms")
        cursor.execute("DROP TABLE IF EXISTS branches")

        # Create branches table
        cursor.execute("""
        CREATE TABLE branches (
            branch_id INTEGER PRIMARY KEY,
            branch_name TEXT NOT NULL UNIQUE
        )
        """)

        # Create courses table
        cursor.execute("""
        CREATE TABLE courses (
            course_code TEXT PRIMARY KEY,
            course_name TEXT NOT NULL,
            branch_name TEXT NOT NULL
        )
        """)

        # Create course_classes table to store the number of classes per course
        cursor.execute("""
        CREATE TABLE course_classes (
            course_code TEXT PRIMARY KEY,
            num_classes INTEGER NOT NULL DEFAULT 2,
            FOREIGN KEY (course_code) REFERENCES courses (course_code)
        )
        """)

        # Create teachers table with branch assignment
        cursor.execute("""
        CREATE TABLE teachers (
            teacher_id INTEGER PRIMARY KEY,
            teacher_name TEXT NOT NULL,
            branch_name TEXT NOT NULL,
            FOREIGN KEY (branch_name) REFERENCES branches (branch_name)
        )
        """)

        # Create rooms table
        cursor.execute("""
        CREATE TABLE rooms (
            room_id INTEGER PRIMARY KEY,
            room_name TEXT NOT NULL UNIQUE
        )
        """)

        # Create branch_teacher_courses table (mapping table)
        cursor.execute("""
        CREATE TABLE branch_teacher_courses (
            id INTEGER PRIMARY KEY,
            branch_id INTEGER,
            teacher_id INTEGER,
            course_code TEXT,
            FOREIGN KEY (branch_id) REFERENCES branches (branch_id),
            FOREIGN KEY (teacher_id) REFERENCES teachers (teacher_id),
            FOREIGN KEY (course_code) REFERENCES courses (course_code)
        )
        """)

        # Create timetable table
        cursor.execute("""
        CREATE TABLE timetable (
            id INTEGER PRIMARY KEY,
            course_code TEXT,
            course_name TEXT,
            teacher TEXT,
            room TEXT,
            branch TEXT,
            day INTEGER,
            slot INTEGER,
            class_index INTEGER,  -- To track multiple classes in the same slot
            FOREIGN KEY (course_code) REFERENCES courses (course_code)
        )
        """)

        # Add sample data
        # Add branches
        branches = [
            ("CSE",),
            ("ME",),
            ("ECE",),
            ("CE",),
            ("EEE",)
        ]
        cursor.executemany("INSERT INTO branches (branch_name) VALUES (?)", branches)

        # Get branch IDs
        cursor.execute("SELECT branch_id, branch_name FROM branches")
        branch_ids = {name: id for id, name in cursor.fetchall()}

        # Add rooms
        rooms = [
            ("Room 101",),
            ("Room 102",),
            ("Room 103",),
            ("Room 104",),
            ("Room 105",),
            ("Room 201",),
            ("Room 202",),
            ("Room 203",),
            ("Room 204",),
            ("Room 205",)
        ]
        cursor.executemany("INSERT INTO rooms (room_name) VALUES (?)", rooms)

        # Add courses with branch association
        courses = [
            # CSE courses
            ("CSE101", "Data Structures", "CSE"),
            ("CSE102", "Operating Systems", "CSE"),
            ("CSE103", "Algorithms", "CSE"),
            ("CSE104", "Database Systems", "CSE"),
            ("CSE105", "Computer Networks", "CSE"),

            # ME courses
            ("ME101", "Thermodynamics", "ME"),
            ("ME102", "Fluid Mechanics", "ME"),
            ("ME103", "Machine Design", "ME"),
            ("ME104", "Heat Transfer", "ME"),
            ("ME105", "Manufacturing Processes", "ME"),

            # ECE courses
            ("ECE101", "Digital Electronics", "ECE"),
            ("ECE102", "Analog Circuits", "ECE"),
            ("ECE103", "Signals and Systems", "ECE"),
            ("ECE104", "Communication Systems", "ECE"),
            ("ECE105", "Microprocessors", "ECE"),

            # CE courses
            ("CE101", "Structural Analysis", "CE"),
            ("CE102", "Geotechnical Engineering", "CE"),
            ("CE103", "Transportation Engineering", "CE"),
            ("CE104", "Environmental Engineering", "CE"),
            ("CE105", "Construction Management", "CE"),

            # EEE courses
            ("EEE101", "Power Systems", "EEE"),
            ("EEE102", "Control Systems", "EEE"),
            ("EEE103", "Electrical Machines", "EEE"),
            ("EEE104", "Power Electronics", "EEE"),
            ("EEE105", "High Voltage Engineering", "EEE")
        ]
        cursor.executemany("INSERT INTO courses (course_code, course_name, branch_name) VALUES (?, ?, ?)", courses)

        # Initialize course_classes table with default values (2 classes per week for each course)
        for course_code, _, _ in courses:
            cursor.execute("INSERT INTO course_classes (course_code, num_classes) VALUES (?, ?)", (course_code, 2))

        # Add teachers with branch assignments
        teachers = [
            # CSE teachers
            ("Prof. Smith", "CSE"),
            ("Prof. Johnson", "CSE"),
            ("Prof. Williams", "CSE"),
            ("Prof. Brown", "CSE"),

            # ME teachers
            ("Prof. Jones", "ME"),
            ("Prof. Miller", "ME"),
            ("Prof. Davis", "ME"),
            ("Prof. Garcia", "ME"),

            # ECE teachers
            ("Prof. Rodriguez", "ECE"),
            ("Prof. Wilson", "ECE"),
            ("Prof. Martinez", "ECE"),
            ("Prof. Anderson", "ECE"),

            # CE teachers
            ("Prof. Taylor", "CE"),
            ("Prof. Thomas", "CE"),
            ("Prof. Hernandez", "CE"),
            ("Prof. Moore", "CE"),

            # EEE teachers
            ("Prof. Martin", "EEE"),
            ("Prof. Jackson", "EEE"),
            ("Prof. Thompson", "EEE"),
            ("Prof. White", "EEE")
        ]
        cursor.executemany("INSERT INTO teachers (teacher_name, branch_name) VALUES (?, ?)", teachers)

        # Get teacher IDs with their branch
        cursor.execute("SELECT teacher_id, teacher_name, branch_name FROM teachers")
        teachers_data = cursor.fetchall()

        # Create dictionaries for easy lookup
        teacher_ids = {name: id for id, name, _ in teachers_data}
        teacher_branches = {id: branch for id, _, branch in teachers_data}

        # Group teachers by branch
        branch_teachers = {}
        for teacher_id, _, branch in teachers_data:
            if branch not in branch_teachers:
                branch_teachers[branch] = []
            branch_teachers[branch].append(teacher_id)

        # Create branch-teacher-course mappings
        # Each teacher can teach multiple courses in their branch
        mappings = []

        # For each branch
        for branch_name, branch_id in branch_ids.items():
            # Get courses for this branch
            cursor.execute("SELECT course_code FROM courses WHERE branch_name = ?", (branch_name,))
            branch_courses = [row[0] for row in cursor.fetchall()]

            # Get teachers for this branch
            if branch_name not in branch_teachers or not branch_teachers[branch_name]:
                print(f"Warning: No teachers assigned to branch {branch_name}")
                continue

            branch_teacher_ids = branch_teachers[branch_name]

            # Assign teachers to courses for this branch
            # Each course should have at least 2 teachers who can teach it (or all teachers if fewer than 2)
            for course_code in branch_courses:
                # Select 2-3 random teachers for this course (or all if fewer)
                num_teachers = min(len(branch_teacher_ids), random.randint(2, 3))
                selected_teachers = random.sample(branch_teacher_ids, num_teachers)

                for teacher_id in selected_teachers:
                    # Verify teacher belongs to this branch
                    if teacher_branches[teacher_id] == branch_name:
                        mappings.append((branch_id, teacher_id, course_code))

        # Insert mappings
        cursor.executemany(
            "INSERT INTO branch_teacher_courses (branch_id, teacher_id, course_code) VALUES (?, ?, ?)",
            mappings
        )

        conn.commit()
        print(" Database initialized successfully with sample data!")
        print(f"Added {len(branches)} branches, {len(rooms)} rooms, {len(courses)} courses, {len(teachers)} teachers, and {len(mappings)} branch-teacher-course mappings.")