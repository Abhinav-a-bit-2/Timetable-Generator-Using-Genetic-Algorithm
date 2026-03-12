import sqlite3
from db_operations import delete_course, delete_course_teacher_mapping, add_course, add_branch_teacher_course_mapping

# Linked List implementation for course management
class CourseNode:
    def __init__(self, course_code, course_name, branch_name):
        self.course_code = course_code
        self.course_name = course_name
        self.branch_name = branch_name
        self.next = None
        self.prev = None

class CourseList:
    def __init__(self):
        self.head = None
        self.tail = None
        self.size = 0
        self.load_courses_from_db()
    
    def load_courses_from_db(self):
        """Load all courses from the database into the linked list."""
        with sqlite3.connect("timetable.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT course_code, course_name, branch_name FROM courses ORDER BY branch_name, course_code")
            courses = cursor.fetchall()
            
            # Clear existing list
            self.head = None
            self.tail = None
            self.size = 0
            
            # Add each course to the linked list
            for course_code, course_name, branch_name in courses:
                self.append(course_code, course_name, branch_name)
    
    def append(self, course_code, course_name, branch_name):
        """Add a new course to the end of the linked list."""
        new_node = CourseNode(course_code, course_name, branch_name)
        if not self.head:
            self.head = new_node
            self.tail = new_node
        else:
            new_node.prev = self.tail
            self.tail.next = new_node
            self.tail = new_node
        self.size += 1
    
    def find_course(self, course_code):
        """Find a course by its code."""
        current = self.head
        while current:
            if current.course_code == course_code:
                return current
            current = current.next
        return None
    
    def delete_course(self, course_code):
        """Delete a course from the linked list and database."""
        # First delete from database
        if delete_course(course_code):
            # If successful, remove from linked list
            node = self.find_course(course_code)
            if node:
                if node.prev:
                    node.prev.next = node.next
                else:
                    self.head = node.next
                
                if node.next:
                    node.next.prev = node.prev
                else:
                    self.tail = node.prev
                
                self.size -= 1
                return True
        return False
    
    def display_courses(self):
        """Display all courses in the linked list."""
        if not self.head:
            print("No courses found.")
            return
        
        print("\n=== Courses List ===")
        print(f"{'Course Code':<12} | {'Course Name':<30} | {'Branch':<10}")
        print("-" * 60)
        
        current = self.head
        while current:
            print(f"{current.course_code:<12} | {current.course_name:<30} | {current.branch_name:<10}")
            current = current.next
        
        print(f"\nTotal courses: {self.size}")

# Linked List implementation for course-teacher mappings
class MappingNode:
    def __init__(self, mapping_id, branch_name, teacher_name, course_code):
        self.mapping_id = mapping_id
        self.branch_name = branch_name
        self.teacher_name = teacher_name
        self.course_code = course_code
        self.next = None
        self.prev = None

class MappingList:
    def __init__(self):
        self.head = None
        self.tail = None
        self.size = 0
        self.load_mappings_from_db()
    
    def load_mappings_from_db(self):
        """Load all course-teacher mappings from the database into the linked list."""
        with sqlite3.connect("timetable.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT btc.id, b.branch_name, t.teacher_name, btc.course_code
                FROM branch_teacher_courses btc
                JOIN branches b ON btc.branch_id = b.branch_id
                JOIN teachers t ON btc.teacher_id = t.teacher_id
                ORDER BY b.branch_name, t.teacher_name, btc.course_code
            """)
            mappings = cursor.fetchall()
            
            # Clear existing list
            self.head = None
            self.tail = None
            self.size = 0
            
            # Add each mapping to the linked list
            for mapping_id, branch_name, teacher_name, course_code in mappings:
                self.append(mapping_id, branch_name, teacher_name, course_code)
    
    def append(self, mapping_id, branch_name, teacher_name, course_code):
        """Add a new mapping to the end of the linked list."""
        new_node = MappingNode(mapping_id, branch_name, teacher_name, course_code)
        if not self.head:
            self.head = new_node
            self.tail = new_node
        else:
            new_node.prev = self.tail
            self.tail.next = new_node
            self.tail = new_node
        self.size += 1
    
    def find_mapping(self, branch_name, teacher_name, course_code):
        """Find a mapping by branch, teacher, and course."""
        current = self.head
        while current:
            if (current.branch_name == branch_name and 
                current.teacher_name == teacher_name and 
                current.course_code == course_code):
                return current
            current = current.next
        return None
    
    def delete_mapping(self, branch_name, teacher_name, course_code):
        """Delete a mapping from the linked list and database."""
        # First delete from database
        if delete_course_teacher_mapping(branch_name, teacher_name, course_code):
            # If successful, remove from linked list
            node = self.find_mapping(branch_name, teacher_name, course_code)
            if node:
                if node.prev:
                    node.prev.next = node.next
                else:
                    self.head = node.next
                
                if node.next:
                    node.next.prev = node.prev
                else:
                    self.tail = node.prev
                
                self.size -= 1
                return True
        return False
    
    def display_mappings(self, filter_branch=None, filter_teacher=None, filter_course=None):
        """Display mappings with optional filters."""
        if not self.head:
            print("No mappings found.")
            return
        
        print("\n=== Course-Teacher Mappings ===")
        if filter_branch:
            print(f"Filtered by Branch: {filter_branch}")
        if filter_teacher:
            print(f"Filtered by Teacher: {filter_teacher}")
        if filter_course:
            print(f"Filtered by Course: {filter_course}")
        
        print(f"{'Branch':<10} | {'Teacher':<20} | {'Course Code':<12} | {'Mapping ID':<10}")
        print("-" * 60)
        
        count = 0
        current = self.head
        while current:
            # Apply filters if provided
            if ((not filter_branch or current.branch_name == filter_branch) and
                (not filter_teacher or current.teacher_name == filter_teacher) and
                (not filter_course or current.course_code == filter_course)):
                
                print(f"{current.branch_name:<10} | {current.teacher_name:<20} | {current.course_code:<12} | {current.mapping_id:<10}")
                count += 1
            
            current = current.next
        
        print(f"\nDisplayed mappings: {count} (Total: {self.size})")

def main_menu():
    """Display the main menu for course management."""
    course_list = CourseList()
    mapping_list = MappingList()
    
    while True:
        print("\n===== Course Management System =====")
        print("1. View All Courses")
        print("2. Add New Course")
        print("3. Delete Course")
        print("4. View Course-Teacher Mappings")
        print("5. Add Course-Teacher Mapping")
        print("6. Delete Course-Teacher Mapping")
        print("0. Exit")
        
        choice = input("\nEnter your choice (0-6): ")
        
        if choice == '0':
            print("Exiting Course Management System...")
            break
        
        elif choice == '1':
            course_list.load_courses_from_db()  # Refresh from database
            course_list.display_courses()
        
        elif choice == '2':
            course_code = input("Enter course code: ")
            course_name = input("Enter course name: ")
            branch_name = input("Enter branch name: ")
            
            # Add course to database
            with sqlite3.connect("timetable.db") as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        "INSERT INTO courses (course_code, course_name, branch_name) VALUES (?, ?, ?)",
                        (course_code, course_name, branch_name)
                    )
                    conn.commit()
                    print(f"✅ Course '{course_code}' added successfully!")
                    
                    # Refresh course list
                    course_list.load_courses_from_db()
                except sqlite3.Error as e:
                    print(f"❌ Database error: {e}")
        
        elif choice == '3':
            course_code = input("Enter course code to delete: ")
            
            # Confirm deletion
            confirm = input(f"Are you sure you want to delete course '{course_code}'? (y/n): ")
            if confirm.lower() == 'y':
                if course_list.delete_course(course_code):
                    # Refresh mapping list as well since mappings were deleted
                    mapping_list.load_mappings_from_db()
            else:
                print("Deletion cancelled.")
        
        elif choice == '4':
            print("\nFilter options (leave blank for no filter):")
            filter_branch = input("Filter by branch: ")
            filter_teacher = input("Filter by teacher: ")
            filter_course = input("Filter by course code: ")
            
            mapping_list.load_mappings_from_db()  # Refresh from database
            mapping_list.display_mappings(
                filter_branch if filter_branch else None,
                filter_teacher if filter_teacher else None,
                filter_course if filter_course else None
            )
        
        elif choice == '5':
            branch_name = input("Enter branch name: ")
            teacher_name = input("Enter teacher name: ")
            course_code = input("Enter course code: ")
            
            if add_branch_teacher_course_mapping(branch_name, teacher_name, course_code):
                # Refresh mapping list
                mapping_list.load_mappings_from_db()
        
        elif choice == '6':
            branch_name = input("Enter branch name: ")
            teacher_name = input("Enter teacher name: ")
            course_code = input("Enter course code: ")
            
            # Confirm deletion
            confirm = input(f"Are you sure you want to delete this mapping? (y/n): ")
            if confirm.lower() == 'y':
                mapping_list.delete_mapping(branch_name, teacher_name, course_code)
            else:
                print("Deletion cancelled.")
        
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main_menu()