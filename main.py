from simplified_genetic_algorithm import genetic_algorithm, print_timetable, print_professor_schedules
import sqlite3

# helper to open the database using the path from db_operations

def _connect():
    return sqlite3.connect(DB_PATH)

# Import functions from db_operations
from db_operations import add_professor, add_course, check_teacher_by_course_code, fetch_data_from_db, DB_PATH
from db_operations import add_branch, add_branch_teacher_course_mapping, initialize_database
from db_operations import delete_course, delete_course_teacher_mapping


def check_course_code_exists(course_code):
    """Check if a specific course code exists in the courses table."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT course_code FROM courses WHERE course_code = ?", (course_code,))
            result = cursor.fetchone()

            if result:
                print(f" Course code '{course_code}' exists in the database.")
                return True
            else:
                print(f" Course code '{course_code}' does not exist in the database.")
                return False

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False


def get_branches():
    """Get all branches from the database."""
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT branch_name FROM branches")
        branches = [branch[0] for branch in cursor.fetchall()]

        # Print debug information
        print(f"Fetched branches: {branches}")

    return branches


def debug_database():
    """Debug function to check database contents."""
    courses, teachers, rooms = fetch_data_from_db()

    print("\n--- Database Contents ---")
    print(f"Courses: {len(courses)}")
    for i, course in enumerate(courses[:5]):  # Show first 5
        print(f"  {i + 1}. {course}")

    print(f"\nTeachers: {len(teachers)}")
    for i, teacher in enumerate(teachers[:5]):  # Show first 5
        print(f"  {i + 1}. {teacher}")

    print(f"\nRooms: {len(rooms)}")
    for i, room in enumerate(rooms[:5]):  # Show first 5
        print(f"  {i + 1}. {room}")

    # Check branch-teacher-course mappings
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.branch_name, t.teacher_name, c.course_code, c.course_name
            FROM branch_teacher_courses btc
            JOIN branches b ON btc.branch_id = b.branch_id
            JOIN teachers t ON btc.teacher_id = t.teacher_id
            JOIN courses c ON btc.course_code = c.course_code
            LIMIT 10
        """)
        mappings = cursor.fetchall()

        print(f"\nBranch-Teacher-Course Mappings: {len(mappings)}")
        for i, mapping in enumerate(mappings[:10]):  # Show first 10
            print(f"  {i + 1}. Branch: {mapping[0]}, Teacher: {mapping[1]}, Course: {mapping[2]} ({mapping[3]})")


def verify_database_integrity():
    """Verify that the database has enough valid data for timetable generation."""
    with _connect() as conn:
        cursor = conn.cursor()

        # Check if each branch has courses
        cursor.execute("""
            SELECT b.branch_name, COUNT(c.course_code)
            FROM branches b
            LEFT JOIN courses c ON b.branch_name = c.branch_name
            GROUP BY b.branch_name
        """)
        branch_courses = cursor.fetchall()

        print("\n--- Branch Course Counts ---")
        for branch, count in branch_courses:
            status = "✅" if count > 0 else "❌"
            print(f"{status} {branch}: {count} courses")

        # Check if each course has teachers
        cursor.execute("""
            SELECT c.course_code, c.course_name, COUNT(btc.teacher_id)
            FROM courses c
            LEFT JOIN branch_teacher_courses btc ON c.course_code = btc.course_code
            GROUP BY c.course_code
        """)
        course_teachers = cursor.fetchall()

        print("\n--- Course Teacher Counts ---")
        for course_code, course_name, count in course_teachers:
            status = "✅" if count > 0 else "❌"
            print(f"{status} {course_code} ({course_name}): {count} teachers")

        # Check if each branch has teacher-course mappings
        cursor.execute("""
            SELECT b.branch_name, COUNT(btc.id)
            FROM branches b
            LEFT JOIN branch_teacher_courses btc ON b.branch_id = btc.branch_id
            GROUP BY b.branch_name
        """)
        branch_mappings = cursor.fetchall()

        print("\n--- Branch Mapping Counts ---")
        for branch, count in branch_mappings:
            status = "✅" if count > 0 else "❌"
            print(f"{status} {branch}: {count} teacher-course mappings")

        # Check for any issues
        issues = False
        for _, count in branch_courses:
            if count == 0:
                issues = True
        for _, _, count in course_teachers:
            if count == 0:
                issues = True
        for _, count in branch_mappings:
            if count == 0:
                issues = True

        if issues:
            print("\n❌ Some issues were found with the data. Please fix them before generating a timetable.")
            return False
        else:
            print("\n✅ All data looks valid for timetable generation!")
            return True


def populate_database_menu():
    """Menu for database population options."""
    while True:
        print("\n--- Database Population Menu ---")
        print("1. Add Branch")
        print("2. Add Course")
        print("3. Add Professor")
        print("4. Add Branch-Teacher-Course Mapping")
        print("5. Delete Course")
        print("6. Delete Course-Teacher Mapping")
        print("7. Run Database Population Script")
        print("8. Verify Database Integrity")
        print("9. Return to Main Menu")

        choice = input("Enter your choice: ")

        if choice == "1":
            branch_name = input("Enter branch name: ")
            add_branch(branch_name)

        elif choice == "2":
            course_code = input("Enter course code: ")
            course_name = input("Enter course name: ")
            branch_name = input("Enter branch name: ")

            # Check if branch exists
            with _connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT branch_id FROM branches WHERE branch_name = ?", (branch_name,))
                if not cursor.fetchone():
                    print(f"❌ Branch '{branch_name}' does not exist. Please add it first.")
                    continue

            # Add course with branch
            with _connect() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        "INSERT INTO courses (course_code, course_name, branch_name) VALUES (?, ?, ?)",
                        (course_code, course_name, branch_name)
                    )
                    conn.commit()
                    print(f"✅ Course '{course_code}' added successfully!")
                except sqlite3.Error as e:
                    print(f"Database error: {e}")

        elif choice == "3":
            teacher_name = input("Enter professor's name: ")

            # List branches for selection
            branches = get_branches()
            if not branches:
                print("❌ No branches found. Please add branches first.")
                continue

            print("\nAvailable branches:")
            for i, branch in enumerate(branches):
                print(f"{i + 1}. {branch}")

            branch_idx = int(input("Select branch for this professor (number): ")) - 1
            if branch_idx < 0 or branch_idx >= len(branches):
                print("Invalid selection.")
                continue

            branch_name = branches[branch_idx]

            # Add teacher with branch assignment
            add_professor(teacher_name, branch_name)

        elif choice == "4":
            # List branches
            branches = get_branches()
            if not branches:
                print("❌ No branches found. Please add branches first.")
                continue

            print("\nAvailable branches:")
            for i, branch in enumerate(branches):
                print(f"{i + 1}. {branch}")

            branch_idx = int(input("Select branch (number): ")) - 1
            if branch_idx < 0 or branch_idx >= len(branches):
                print("Invalid selection.")
                continue

            branch_name = branches[branch_idx]

            # List teachers
            with _connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT teacher_id, teacher_name FROM teachers")
                teachers = cursor.fetchall()

            if not teachers:
                print("❌ No teachers found. Please add teachers first.")
                continue

            print("\nAvailable teachers:")
            for i, (_, teacher) in enumerate(teachers):
                print(f"{i + 1}. {teacher}")

            teacher_idx = int(input("Select teacher (number): ")) - 1
            if teacher_idx < 0 or teacher_idx >= len(teachers):
                print("Invalid selection.")
                continue

            teacher_name = teachers[teacher_idx][1]

            # List courses for the selected branch
            with _connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT course_code, course_name FROM courses WHERE branch_name = ?", (branch_name,))
                courses = cursor.fetchall()

            if not courses:
                print(f"❌ No courses found for branch {branch_name}. Please add courses first.")
                continue

            print("\nAvailable courses for branch " + branch_name + ":")
            for i, (code, name) in enumerate(courses):
                print(f"{i + 1}. {code}: {name}")

            course_idx = int(input("Select course (number): ")) - 1
            if course_idx < 0 or course_idx >= len(courses):
                print("Invalid selection.")
                continue

            course_code = courses[course_idx][0]

            # Add mapping
            add_branch_teacher_course_mapping(branch_name, teacher_name, course_code)

        elif choice == "5":
            # Import delete_course function
            from db_operations import delete_course

            # List all courses
            with _connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT course_code, course_name, branch_name FROM courses ORDER BY branch_name, course_code")
                courses = cursor.fetchall()

            if not courses:
                print("❌ No courses found in the database.")
                continue

            print("\nAvailable courses:")
            for i, (code, name, branch) in enumerate(courses):
                print(f"{i + 1}. [{branch}] {code}: {name}")

            course_idx = int(input("Select course to delete (number): ")) - 1
            if course_idx < 0 or course_idx >= len(courses):
                print("Invalid selection.")
                continue

            course_code = courses[course_idx][0]

            # Confirm deletion
            confirm = input(f"Are you sure you want to delete course '{course_code}'? This will also delete all mappings. (y/n): ")
            if confirm.lower() == 'y':
                delete_course(course_code)
            else:
                print("Deletion cancelled.")

        elif choice == "6":
            # Import delete_course_teacher_mapping function
            from db_operations import delete_course_teacher_mapping

            # List all mappings
            with _connect() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT btc.id, b.branch_name, t.teacher_name, c.course_code, c.course_name
                    FROM branch_teacher_courses btc
                    JOIN branches b ON btc.branch_id = b.branch_id
                    JOIN teachers t ON btc.teacher_id = t.teacher_id
                    JOIN courses c ON btc.course_code = c.course_code
                    ORDER BY b.branch_name, t.teacher_name, c.course_code
                """)
                mappings = cursor.fetchall()

            if not mappings:
                print("❌ No course-teacher mappings found in the database.")
                continue

            print("\nAvailable mappings:")
            for i, (id, branch, teacher, code, name) in enumerate(mappings):
                print(f"{i + 1}. [{branch}] {teacher} - {code}: {name}")

            mapping_idx = int(input("Select mapping to delete (number): ")) - 1
            if mapping_idx < 0 or mapping_idx >= len(mappings):
                print("Invalid selection.")
                continue

            mapping = mappings[mapping_idx]
            branch_name = mapping[1]
            teacher_name = mapping[2]
            course_code = mapping[3]

            # Confirm deletion
            confirm = input(f"Are you sure you want to delete this mapping? (y/n): ")
            if confirm.lower() == 'y':
                delete_course_teacher_mapping(branch_name, teacher_name, course_code)
            else:
                print("Deletion cancelled.")

        elif choice == "7":
            print("This will run the database population script.")
            print("WARNING: This will reset your database and populate it with sample data.")
            confirm = input("Do you want to continue? (y/n): ")

            if confirm.lower() == 'y':
                # Import and run the population script
                try:
                    from populate_database import main as populate_main
                    populate_main()
                except ImportError:
                    print("❌ Could not find the populate_database.py script.")
                    print("Please make sure it's in the same directory as main.py.")

        elif choice == "8":
            verify_database_integrity()

        elif choice == "9":
            return

        else:
            print("Invalid choice. Please try again.")


def main():
    """Main function to run the timetable generation system."""
    from db_operations import initialize_database

    # Initialize database with sample data
    print("\nInitializing database with sample data...")
    initialize_database()
    print("Database initialized successfully!")

    while True:
        print("\n=== Timetable Generation System ===")
        print("1. Reinitialize Database with Sample Data")
        print("2. Populate Database Manually")
        print("3. Course Management (Add/Delete Courses & Mappings)")
        print("4. Course Classes Management (Set Number of Classes per Course)")
        print("5. Generate Timetable")
        print("6. View Generated Timetable")
        print("7. View Professor Schedules")
        print("8. Debug Database")
        print("9. Exit")

        choice = input("\nEnter your choice: ")

        if choice == "1":
            print("\nReinitializing database with sample data...")
            initialize_database()
            print("Database reinitialized successfully!")

        elif choice == "2":
            populate_database_menu()

        elif choice == "3":
            # Launch the course management system
            from course_management import main_menu
            main_menu()

        elif choice == "4":
            # Launch the course classes management system
            from course_classes_management import main_menu
            main_menu()

        elif choice == "5":
            # Verify database integrity first
            if not verify_database_integrity():
                print("Please fix the database issues before generating a timetable.")
                continue

            # Get branches
            branches = get_branches()
            if not branches:
                print(" No branches found. Please add branches first.")
                continue

            print("\nGenerating timetable...")
            result = genetic_algorithm(branches, generations=100)

            if result:
                schedule, professor_schedules = result
                # Store professor schedules in a global variable for later access
                globals()['last_professor_schedules'] = professor_schedules

                print("\nTimetable generated successfully!")
                print_timetable(schedule)

                # Ask if user wants to see professor schedules
                show_prof = input("\nDo you want to see professor schedules? (y/n): ")
                if show_prof.lower() == 'y':
                    print_professor_schedules(professor_schedules)
            else:
                print("\nFailed to generate a valid timetable.")

        elif choice == "6":
            from view_timetable import main as view_timetable_main
            view_timetable_main()

        elif choice == "7":
            # Create a global variable to store professor schedules
            if 'last_professor_schedules' in globals() and globals()['last_professor_schedules']:
                print_professor_schedules(globals()['last_professor_schedules'])
            else:
                print("\nNo professor schedules available. Please generate a timetable first.")

        elif choice == "8":
            debug_database()

        elif choice == "9":
            print("\nThank you for using the Timetable Generation System!")
            break

        else:
            print("\nInvalid choice. Please try again.")


# Entry point of the script
if __name__ == "__main__":
    main()