"""
Simplified Genetic Algorithm for Timetable Generation

This module implements a genetic algorithm to generate optimal timetables
for educational institutions. It handles multiple branches, teachers, courses,
and rooms while ensuring each professor has the required number of classes
for each course they teach.

Author: Timetable Generator Team
Version: 1.1
"""
import cProfile
# Importing all the libraries we need for our program
import random  # for generating random numbers
import timeit
import copy    # for making deep copies of objects
import time    # to measure how long our algorithm takes
import heapq   # this helps us with priority queues
from db_operations import fetch_data_from_db, insert_timetable_into_db, get_course_classes
import sqlite3  # for database operations
from tabulate import tabulate  # makes our tables look nice when printed
from collections import defaultdict, Counter  # special dictionaries that are helpful

# TODO: Learn about more efficient data structures for scheduling problems

# Constants for our timetable
DAYS = 5  # Monday to Friday
SLOTS_PER_DAY = 9  # 9 time slots per day
LUNCH_SLOT = 4  # Lunch break (5th slot)
POPULATION_SIZE = 30  # Population size for genetic algorithm
ELITE_SIZE = 6  # Top schedules to keep unchanged
TOURNAMENT_SIZE = 4  # Number of schedules to compete in tournament selection
MUTATION_RATE = 0.25  # Probability of mutation
CROSSOVER_RATE = 0.8  # Probability of crossover
MAX_CLASSES_PER_SLOT = 3  # Maximum number of classes in a single time slot

# Preferred time slots - morning slots (0-3) are preferred for core subjects
# This encourages important classes to be scheduled in the morning
PREFERRED_MORNING_SLOTS = [0, 1, 2, 3]  # First 4 slots of the day

# List of core courses that should preferably be scheduled in the morning
# These are typically more demanding subjects that benefit from morning scheduling
CORE_COURSES = ["CSE101", "ECE101", "ME101", "CE101", "EEE101"]

# Class to store class data
class ClassSlot:
    def __init__(self, course_code, course_name, teacher, room, branch, day, slot):
        # Store all the information about a class
        self.course_code = course_code
        self.course_name = course_name
        self.teacher = teacher
        self.room = room
        self.branch = branch
        self.day = day
        self.slot = slot
        # print(f"Created new class: {course_code} with {teacher}")

    def __str__(self):
        # This helps us print the class in a readable format
        return f"{self.course_code}: {self.teacher} in {self.room} ({self.branch})"

    def copy(self):
        return ClassSlot(
            self.course_code,
            self.course_name,
            self.teacher,
            self.room,
            self.branch,
            self.day,
            self.slot
        )



def copy_schedule(schedule):
    if isinstance(schedule, dict):
        return {
            key: [cls.copy() for cls in class_list]
            for key, class_list in schedule.items()
        }
    elif isinstance(schedule, list):
        return [cls.copy() for cls in schedule]
    else:
        raise TypeError("Unsupported schedule format")



def create_empty_schedule():
    """Create an empty schedule with None values."""
    # This creates a 2D array filled with None values
    # First we make DAYS number of rows
    empty_schedule = []
    for i in range(DAYS):
        # Then for each day, we add SLOTS_PER_DAY number of None values
        day_slots = []
        for j in range(SLOTS_PER_DAY):
            day_slots.append(None)
        empty_schedule.append(day_slots)
    # return [[None for _ in range(SLOTS_PER_DAY)] for _ in range(DAYS)]
    return empty_schedule

def check_room_conflicts(schedule):
    """Check for room conflicts in the schedule.

    This function identifies instances where the same room is assigned to multiple
    classes at the same time. It's optimized for performance using sets and
    handles all possible schedule data formats.

    Args:
        schedule: The timetable schedule to check

    Returns:
        A list of conflicts (day, slot, room) or an empty list if no conflicts
    """
    # Handle None schedule case
    if schedule is None:
        return []

    conflicts = []

    # Pre-allocate a 2D array to track room usage across all days and slots
    # This is more efficient than creating new sets in each iteration
    room_usage = [[set() for _ in range(SLOTS_PER_DAY)] for _ in range(DAYS)]

    # First pass: collect all room usage
    for day in range(DAYS):
        for slot in range(SLOTS_PER_DAY):
            # Skip lunch slot
            if slot == LUNCH_SLOT:
                continue

            # Skip empty slots
            if schedule[day][slot] is None:
                continue

            # Handle multiple classes in the same slot
            classes = schedule[day][slot] if isinstance(schedule[day][slot], list) else [schedule[day][slot]]

            for class_data in classes:
                if class_data is None:
                    continue
                # Extract room information, handling both object and tuple formats
                room = class_data.room if hasattr(class_data, 'room') else class_data[3]
                # Check for conflict and add to room usage
                if room in room_usage[day][slot]:
                    conflicts.append((day, slot, room))
                room_usage[day][slot].add(room)
    return conflicts
def get_course_class_requirements():
    """Get the number of classes required for each course.
    Returns a dictionary mapping course_code to the number of classes required.
    """
    try:
        # Get num course class from the database
        course_classes = get_course_classes()
        # Create a dictionary
        class_requirements = {}
        # Loop through each course and store its requirements
        for course_code, num_classes, _, _ in course_classes:
            num_classes_int = int(num_classes)
            # Store the requirement in our dictionary
            class_requirements[course_code] = num_classes_int
            # Print out the requirement for debugging
        #    print(f"Course {course_code} requires {num_classes} classes")
        return class_requirements
    except Exception as e:
        # If there's an error, print it and use a default value
        print(f"Error getting course classes: {e}")

        # If there's an error, use a default of 1 class per course
        return defaultdict(lambda: 1)

def fix_overassigned_classes(schedule):
    """Fix a schedule by removing extra classes for teachers who have more than required.
    Optimized using a heap (priority queue) to efficiently process the most overassigned classes first.
    """
    fixed_schedule = copy_schedule(schedule)
    class_requirements = get_course_class_requirements()
    teacher_count = count_course_teacher_classes(fixed_schedule)

    # Use a heap (priority queue) to efficiently track the most overassigned classes
    overassigned_heap = []

    for (course_code, teacher), count in teacher_count.items():
        required = class_requirements.get(course_code, 1)
        if count > required:
            # Negative extra for max-heap behavior (Python's heapq is a min-heap)
            extra = count - required
            heapq.heappush(overassigned_heap, (-extra, course_code, teacher, count, required))

    if not overassigned_heap:
        return fixed_schedule

    # Process overassigned classes in order of most overassigned first
    while overassigned_heap:
        neg_extra, course_code, teacher, count, required = heapq.heappop(overassigned_heap)
        extra = -neg_extra  # Convert back to positive

        # Find all slots with this course and teacher
        course_slots = []
        for day in range(DAYS):
            for slot in range(SLOTS_PER_DAY):
                if slot == LUNCH_SLOT or fixed_schedule[day][slot] is None:
                    continue

                if isinstance(fixed_schedule[day][slot], list):
                    for i, class_data in enumerate(fixed_schedule[day][slot]):
                        if (class_data is not None and
                            class_data.course_code == course_code and
                            class_data.teacher == teacher):
                            course_slots.append((day, slot, i, class_data))
                elif (fixed_schedule[day][slot].course_code == course_code and
                      fixed_schedule[day][slot].teacher == teacher):
                    course_slots.append((day, slot, None, fixed_schedule[day][slot]))

        # Shuffle to randomize which classes we remove
        random.shuffle(course_slots)

        # Remove the extra classes
        removed = 0
        for day, slot, idx, _ in course_slots:
            if removed >= extra:
                break

            if idx is None:
                # Single class in this slot
                fixed_schedule[day][slot] = None
            else:
                # Multiple classes in this slot
                fixed_schedule[day][slot].pop(idx)
                if not fixed_schedule[day][slot]:
                    fixed_schedule[day][slot] = None
                elif len(fixed_schedule[day][slot]) == 1:
                    fixed_schedule[day][slot] = fixed_schedule[day][slot][0]

            removed += 1

    return fixed_schedule
start_time = timeit.default_timer()

def fix_class_assignments(schedule, courses, teachers, rooms):
    """Fix a schedule by removing extra classes and adding missing classes."""
    # First, fix over-assigned classes
    fixed_schedule = fix_overassigned_classes(schedule)
    class_requirements = get_course_class_requirements()
    course_teacher_counts = count_course_teacher_classes(fixed_schedule)

    # Use a heap to efficiently track the most underassigned classes
    underassigned_heap = []

    # Find teacher-course combinations with too few classes
    for (course_code, teacher), count in course_teacher_counts.items():
        required = class_requirements.get(course_code, 1)
        if count < required:
            # Negative missing for max-heap behavior (Python's heapq is a min-heap)
            missing = required - count
            heapq.heappush(underassigned_heap, (-missing, course_code, teacher, count, required))

    # Also check for course-teacher combinations that should exist but don't
    try:
        with sqlite3.connect("timetable.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.course_code, c.course_name, b.branch_name, t.teacher_name
                FROM branch_teacher_courses btc
                JOIN branches b ON btc.branch_id = b.branch_id
                JOIN teachers t ON btc.teacher_id = t.teacher_id
                JOIN courses c ON btc.course_code = c.course_code
            """)
            for course_code, course_name, branch, teacher in cursor.fetchall():
                if course_code in class_requirements:
                    required = class_requirements[course_code]
                    actual = course_teacher_counts.get((course_code, teacher), 0)
                    if actual < required:
                        # Check if this combination is already in the heap
                        key = (course_code, teacher)
                        if not any(item[1:3] == key for item in underassigned_heap):
                            missing = required - actual
                            heapq.heappush(underassigned_heap, (-missing, course_code, teacher, actual, required))
    except sqlite3.Error:
        pass

    if not underassigned_heap:
        return fixed_schedule

    # Track which slots are used for each teacher, room, and branch
    teacher_slots = defaultdict(set)  # teacher -> set of (day, slot)
    room_slots = defaultdict(set)     # room -> set of (day, slot)
    branch_slots = defaultdict(set)   # branch -> set of (day, slot)

    # Fill these tracking structures based on the current schedule
    for day in range(DAYS):
        for slot in range(SLOTS_PER_DAY):
            if slot == LUNCH_SLOT or fixed_schedule[day][slot] is None:
                continue

            classes = fixed_schedule[day][slot] if isinstance(fixed_schedule[day][slot], list) else [fixed_schedule[day][slot]]

            for class_data in classes:
                if class_data is None:
                    continue

                if hasattr(class_data, 'teacher'):
                    teacher = class_data.teacher
                    room = class_data.room
                    branch = class_data.branch
                else:
                    teacher = class_data[2]
                    room = class_data[3]
                    branch = class_data[4]

                teacher_slots[teacher].add((day, slot))
                room_slots[room].add((day, slot))
                branch_slots[branch].add((day, slot))

    # Process underassigned classes in order of most underassigned first
    while underassigned_heap:
        neg_missing, course_code, teacher, actual, required = heapq.heappop(underassigned_heap)
        missing = -neg_missing  # Convert back to positive

        # Find the course details
        course_details = None
        for c in courses:
            if c[0] == course_code:
                course_details = c
                break

        if not course_details:
            continue

        _, branch, course_name = course_details

        # Try to add the missing classes
        for _ in range(missing):
            # Try multiple slots to find one that works
            success = False
            for attempt in range(30):
                day = random.randint(0, DAYS-1)
                slot = random.randint(0, SLOTS_PER_DAY-1)

                if slot == LUNCH_SLOT:
                    continue

                # Skip if teacher or branch already has a class in this slot
                if (day, slot) in teacher_slots[teacher] or (day, slot) in branch_slots[branch]:
                    continue

                # Check if slot is available
                if fixed_schedule[day][slot] is not None:
                    if isinstance(fixed_schedule[day][slot], list) and len(fixed_schedule[day][slot]) >= MAX_CLASSES_PER_SLOT:
                        continue  # Slot is full

                # Find available rooms not already used in this slot
                available_rooms = [r for r in rooms if (day, slot) not in room_slots[r]]

                if not available_rooms:
                    continue

                # Pick a room and create a class slot
                room = random.choice(available_rooms)
                class_slot = ClassSlot(course_code, course_name, teacher, room, branch, day, slot)

                # Add to schedule
                if fixed_schedule[day][slot] is None:
                    fixed_schedule[day][slot] = class_slot
                elif isinstance(fixed_schedule[day][slot], list):
                    if len(fixed_schedule[day][slot]) < MAX_CLASSES_PER_SLOT:
                        fixed_schedule[day][slot].append(class_slot)
                    else:
                        continue  # Slot is full
                else:
                    # Convert single class to list
                    fixed_schedule[day][slot] = [fixed_schedule[day][slot], class_slot]

                # Update tracking
                teacher_slots[teacher].add((day, slot))
                room_slots[room].add((day, slot))
                branch_slots[branch].add((day, slot))
                success = True
                break  # Successfully added a class

            if not success:
                # If we couldn't add this class after trying all slots, move on
                break

    return fixed_schedule
print(timeit.default_timer() - start_time)

def get_valid_assignment(schedule, courses, teachers, rooms, day, slot, branch, course_teacher_counts=None, class_requirements=None, specific_course=None, specific_teacher=None):
    """Get a valid course, teacher, and room assignment for a given slot.
    Returns a ClassSlot object or None if no valid assignment is possible
    """
    # Skip lunch slot
    if slot == LUNCH_SLOT:
        return None

    # Check if the slot already has the maximum number of classes
    if schedule[day][slot] is not None:
        if isinstance(schedule[day][slot], list) and len(schedule[day][slot]) >= MAX_CLASSES_PER_SLOT:
            return None

    # Get all entities already in this slot
    slot_courses = set()
    slot_teachers = set()
    slot_rooms = set()
    slot_branches = set()

    if schedule[day][slot] is not None:
        classes = schedule[day][slot] if isinstance(schedule[day][slot], list) else [schedule[day][slot]]
        for class_data in classes:
            if class_data is None:
                continue

            if hasattr(class_data, 'course_code'):
                slot_courses.add(class_data.course_code)
                slot_teachers.add(class_data.teacher)
                slot_rooms.add(class_data.room)
                slot_branches.add(class_data.branch)
            else:
                slot_courses.add(class_data[0])
                slot_teachers.add(class_data[2])
                slot_rooms.add(class_data[3])
                slot_branches.add(class_data[4])

    # If branch is already in this slot, we can't add another course from the same branch
    if branch in slot_branches:
        return None

    # Filter courses for this branch
    if specific_course:
        # If a specific course is requested, only consider that course
        branch_courses = [c for c in courses if c[1] == branch and c[0] == specific_course]
    else:
        branch_courses = [c for c in courses if c[1] == branch and c[0] not in slot_courses]

    if not branch_courses:
        return None

    # If we have course-teacher counts and class requirements, prioritize courses that need more classes
    if course_teacher_counts and class_requirements and not specific_course:
        # Sort courses by how many more classes they need
        branch_courses.sort(key=lambda c: class_requirements.get(c[0], 1) -
                           sum(count for (course, _), count in course_teacher_counts.items() if course == c[0]),
                           reverse=True)
    else:
        # Shuffle for randomness
        random.shuffle(branch_courses)

    # Try each course
    for course in branch_courses:
        course_code, branch_name, course_name = course

        # Find teachers who can teach this course and are not already in this slot
        if specific_teacher:
            # If a specific teacher is requested, only consider that teacher
            available_teachers = [specific_teacher] if specific_teacher not in slot_teachers else []
            # Verify this teacher can teach this course
            teacher_can_teach = False
            for teacher_data in teachers:
                teacher_name, teacher_course_code, teacher_branch = teacher_data
                if teacher_name == specific_teacher and teacher_course_code == course_code and teacher_branch == branch_name:
                    teacher_can_teach = True
                    break
            if not teacher_can_teach:
                available_teachers = []
        else:
            available_teachers = []
            for teacher_data in teachers:
                teacher_name, teacher_course_code, teacher_branch = teacher_data
                if teacher_branch == branch_name and teacher_course_code == course_code and teacher_name not in slot_teachers:
                    available_teachers.append(teacher_name)

        if not available_teachers:
            continue

        # If we have course-teacher counts and class requirements, prioritize teachers who need more classes
        if course_teacher_counts and class_requirements and not specific_teacher:
            # Sort teachers by how many more classes they need to teach for this course
            available_teachers.sort(key=lambda t: class_requirements.get(course_code, 1) -
                                  course_teacher_counts.get((course_code, t), 0),
                                  reverse=True)
        else:
            # Shuffle for randomness
            random.shuffle(available_teachers)

        # Try each teacher
        for teacher in available_teachers:
            # Find available rooms not already in this slot
            available_rooms = [r for r in rooms if r not in slot_rooms]

            if not available_rooms:
                continue

            # Select a random room
            room = random.choice(available_rooms)

            # Create a class slot
            return ClassSlot(course_code, course_name, teacher, room, branch_name, day, slot)

    return None


def create_random_schedule(courses, teachers, rooms):
    """Create a timetable with constraint-based scheduling to ensure professors have correct class counts."""
    schedule = create_empty_schedule()

    # Get all branches
    branches = set()
    for _, branch, _ in courses:
        branches.add(branch)

    # Get course class requirements
    class_requirements = get_course_class_requirements()

    # Track which slots are used for each teacher, room, and branch
    teacher_slots = defaultdict(set)  # teacher -> set of (day, slot)
    room_slots = defaultdict(set)     # room -> set of (day, slot)
    branch_slots = defaultdict(set)   # branch -> set of (day, slot)

    # Track how many classes have been assigned for each course-teacher pair
    course_counts = defaultdict(int)  # course_code -> count
    course_teacher_counts = defaultdict(int)  # (course_code, teacher) -> count

    # Create a list of all course-teacher combinations that need to be scheduled
    combinations = []

    # First, gather all valid course-teacher combinations from the database
    with sqlite3.connect("timetable.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.course_code, c.course_name, b.branch_name, t.teacher_name
            FROM branch_teacher_courses btc
            JOIN branches b ON btc.branch_id = b.branch_id
            JOIN teachers t ON btc.teacher_id = t.teacher_id
            JOIN courses c ON btc.course_code = c.course_code
        """)
        db_mappings = cursor.fetchall()

        # Add all valid combinations to our list
        for course_code, course_name, branch, teacher in db_mappings:
            if course_code in class_requirements:
                required = class_requirements[course_code]
                combinations.append((course_code, course_name, branch, teacher, required))

    # If we couldn't get combinations from the database, create them from the courses and teachers
    if not combinations:
        print("Warning: No course-teacher mappings found in database. Creating from available data.")
        for course_code, required in class_requirements.items():
            # Find all courses with this code
            course_options = [c for c in courses if c[0] == course_code]
            if not course_options:
                continue

            # For each branch that offers this course
            for course in course_options:
                branch = course[1]
                course_name = course[2]

                # Find teachers who can teach this course in this branch
                course_teachers = []
                for teacher_data in teachers:
                    teacher_name, teacher_course, teacher_branch = teacher_data
                    if teacher_course == course_code and teacher_branch == branch:
                        course_teachers.append(teacher_name)

                if not course_teachers:
                    continue

                # Add all valid combinations to our list
                for teacher in course_teachers:
                    combinations.append((course_code, course_name, branch, teacher, required))

    # Shuffle combinations for diversity
    random.shuffle(combinations)

    print(f"Scheduling {len(combinations)} course-teacher combinations...")

    # First pass: Schedule exactly one class for each course-teacher combination
    for course_code, course_name, branch, teacher, required in combinations:
        # Skip if this teacher already has enough classes for this course
        if course_teacher_counts[(course_code, teacher)] >= required:
            continue

        # Find the best days and slots for this class
        day_slot_scores = []

        for day in range(DAYS):
            for slot in range(SLOTS_PER_DAY):
                if slot == LUNCH_SLOT:
                    continue

                # Skip if teacher or branch already has a class in this slot
                if (day, slot) in teacher_slots[teacher] or (day, slot) in branch_slots[branch]:
                    continue

                # Check if slot is available
                if schedule[day][slot] is not None:
                    if isinstance(schedule[day][slot], list) and len(schedule[day][slot]) >= MAX_CLASSES_PER_SLOT:
                        continue  # Slot is full

                # Find available rooms not already used in this slot
                available_rooms = []
                for room in rooms:
                    if (day, slot) not in room_slots[room]:
                        available_rooms.append(room)

                if not available_rooms:
                    continue

                # Calculate a score for this day/slot based on:
                # 1. How many classes are already scheduled at this time
                # 2. How many classes the teacher already has on this day

                # Count classes in this slot
                slot_count = 0
                if schedule[day][slot] is not None:
                    slot_count = 1 if not isinstance(schedule[day][slot], list) else len(schedule[day][slot])

                # Count teacher's classes on this day
                teacher_day_count = sum(1 for d, s in teacher_slots[teacher] if d == day)

                # Calculate score (lower is better)
                score = slot_count * 3 + teacher_day_count * 2

                # Add a small random factor for diversity
                score += random.random()

                # Add to our list of possibilities
                day_slot_scores.append((day, slot, score, available_rooms))

        # Sort by score (ascending)
        day_slot_scores.sort(key=lambda x: x[2])

        # Try to schedule a class
        for day, slot, _, available_rooms in day_slot_scores:
            # Pick a room
            room = random.choice(available_rooms)

            # Create a class slot
            class_slot = ClassSlot(course_code, course_name, teacher, room, branch, day, slot)

            # Add to schedule
            if schedule[day][slot] is None:
                schedule[day][slot] = class_slot
            elif isinstance(schedule[day][slot], list):
                if len(schedule[day][slot]) < MAX_CLASSES_PER_SLOT:
                    schedule[day][slot].append(class_slot)
                else:
                    continue  # Slot is full
            else:
                # Convert single class to list
                schedule[day][slot] = [schedule[day][slot], class_slot]

            # Update tracking
            teacher_slots[teacher].add((day, slot))
            room_slots[room].add((day, slot))
            branch_slots[branch].add((day, slot))
            course_counts[course_code] += 1
            course_teacher_counts[(course_code, teacher)] += 1

            # Successfully scheduled a class
            break

    # Verify all course-teacher combinations have the required number of classes
    missing_combinations = []
    for course_code, course_name, branch, teacher, required in combinations:
        actual = course_teacher_counts[(course_code, teacher)]
        if actual < required:
            missing_combinations.append((course_code, course_name, branch, teacher, required, actual))

    # Second pass: Try to fix any missing classes
    if missing_combinations:
        print(f"Fixing {len(missing_combinations)} missing course-teacher combinations...")

        for course_code, course_name, branch, teacher, required, actual in missing_combinations:
            # Calculate how many more classes we need
            needed = required - actual

            # Try to schedule the needed classes
            for _ in range(needed):
                # Try multiple slots to find one that works
                for attempt in range(30):  # Try up to 30 different slots
                    day = random.randint(0, DAYS-1)
                    slot = random.randint(0, SLOTS_PER_DAY-1)

                    if slot == LUNCH_SLOT:
                        continue

                    # Skip if teacher already has a class in this slot
                    if (day, slot) in teacher_slots[teacher]:
                        continue

                    # Skip if branch already has a class in this slot
                    if (day, slot) in branch_slots[branch]:
                        continue

                    # Check if slot is available
                    if schedule[day][slot] is not None:
                        if isinstance(schedule[day][slot], list) and len(schedule[day][slot]) >= MAX_CLASSES_PER_SLOT:
                            continue  # Slot is full

                    # Find available rooms not already used in this slot
                    available_rooms = []
                    for room in rooms:
                        if (day, slot) not in room_slots[room]:
                            available_rooms.append(room)

                    if not available_rooms:
                        continue

                    # Pick a room
                    room = random.choice(available_rooms)

                    # Create a class slot
                    class_slot = ClassSlot(course_code, course_name, teacher, room, branch, day, slot)

                    # Add to schedule
                    if schedule[day][slot] is None:
                        schedule[day][slot] = class_slot
                    elif isinstance(schedule[day][slot], list):
                        if len(schedule[day][slot]) < MAX_CLASSES_PER_SLOT:
                            schedule[day][slot].append(class_slot)
                        else:
                            continue  # Slot is full
                    else:
                        # Convert single class to list
                        schedule[day][slot] = [schedule[day][slot], class_slot]

                    # Update tracking
                    teacher_slots[teacher].add((day, slot))
                    room_slots[room].add((day, slot))
                    branch_slots[branch].add((day, slot))
                    course_counts[course_code] += 1
                    course_teacher_counts[(course_code, teacher)] += 1

                    # Successfully scheduled a) > 0 class
                    break

    # Final verification
    all_correct = True
    for course_code, course_name, branch, teacher, required in combinations:
        actual = course_teacher_counts[(course_code, teacher)]
        if actual != required:
            all_correct = False
            print(f"Warning: {teacher} teaching {course_code} has {actual} classes instead of {required}")

    if all_correct:
        print("All course-teacher combinations have the correct number of classes!")

    return schedule

def tournament_selection(population):
    """Select a schedule using tournament selection.

    Tournament selection works by randomly selecting a small group of schedules
    and then picking the best one from that group.
    """
    # First, let's remove any None values from the population
    valid_population = []
    for p in population:
        if p is not None:
            valid_population.append(p)
    # Check if we have enough valid schedules for a tournament
    if len(valid_population) < TOURNAMENT_SIZE:
        # Not enough schedules for a tournament
        if len(valid_population) > 0:
            # If we have at least one valid schedule, return a random one
            random_index = random.randint(0, len(valid_population) - 1)
            return valid_population[random_index]
        else:
            # If we have no valid schedules, return None
            return None  # This will be handled by the crossover function

    # Create a tournament by randomly selecting TOURNAMENT_SIZE schedules
    tournament = random.sample(valid_population, TOURNAMENT_SIZE)

    # Find the schedule with the highest fitness in the tournament
    best_schedule = tournament[0]  # Start with the first schedule
    best_fitness_value = fitness(best_schedule)

    # Loop through the rest of the schedules to find the best one
    for i in range(1, len(tournament)):
        current_fitness = fitness(tournament[i])
        if current_fitness > best_fitness_value:
            best_schedule = tournament[i]
            best_fitness_value = current_fitness

    # print(f"DEBUG: Selected schedule with fitness {best_fitness_value}") # Helped track selection

    # Return the best schedule from the tournament
    return best_schedule

def crossover(p1, p2, courses, teachers, rooms):
    """Create a child schedule by intelligently combining two parent schedules."""

    if p1 is None or p2 is None:
        return create_random_schedule(courses, teachers, rooms)

    child = create_empty_schedule()

    # Track current course-teacher assignment counts
    course_teacher_counts = defaultdict(int)
    class_requirements = get_course_class_requirements()

    for day in range(DAYS):
        for slot in range(SLOTS_PER_DAY):
            if slot == LUNCH_SLOT:
                continue

            slot1 = p1[day][slot]
            slot2 = p2[day][slot]

            # Decide which parent's slot is better
            def score_slot(slot_data):
                if slot_data is None:
                    return 0
                if not isinstance(slot_data, list):
                    slot_data = [slot_data]
                score = 0
                for cls in slot_data:
                    key = (cls.course_code, cls.teacher)
                    required = class_requirements.get(cls.course_code, 1)
                    current = course_teacher_counts[key]
                    if current < required:
                        score += 1  # Favor classes that are still under-assigned
                return score

            score1 = score_slot(slot1)
            score2 = score_slot(slot2)

            # Choose the slot with the better score
            selected_slot = slot1 if score1 > score2 else slot2

            if selected_slot is not None:
                selected_copy = copy_schedule(selected_slot)
                child[day][slot] = selected_copy

                # Update counts
                if not isinstance(selected_copy, list):
                    selected_copy = [selected_copy]
                for cls in selected_copy:
                    course_teacher_counts[(cls.course_code, cls.teacher)] += 1

    # Final fix to ensure the child is valid
    return fix_class_assignments(child, courses, teachers, rooms)

import random


def mutate(schedule, courses, teachers, rooms):
    """Mutate a schedule by changing some assignments, prioritizing fixing course requirements."""
    branches = set(branch for _, branch, _ in courses)
    class_requirements = get_course_class_requirements()
    course_counts = count_course_classes(schedule)

    # Identify problem courses where the actual count of classes differs from the required count
    problem_courses = []
    for course_code, required in class_requirements.items():
        actual = course_counts.get(course_code, 0)
        if actual != required:
            problem_courses.append((course_code, actual, required, abs(actual - required)))

    # Determine mutation type based on the presence of problem courses
    if problem_courses and random.random() < 0.7:
        mutation_type = "targeted"
    else:
        mutation_type = random.choice(["single", "single", "swap", "multi"])

    # Handle different mutation types
    if mutation_type == "single":
        day, slot = random.randint(0, DAYS - 1), random.randint(0, SLOTS_PER_DAY - 1)

        # Skip lunch slot
        if slot == LUNCH_SLOT:
            return

        # Randomly select a branch for mutation
        branch = random.choice(list(branches))

        # Skip if the selected slot is already empty
        if schedule[day][slot] is None:
            return

        if isinstance(schedule[day][slot], list):
            schedule[day][slot] = [c for c in schedule[day][slot] if c is not None and c.branch != branch]
            if not schedule[day][slot]:
                schedule[day][slot] = None
            elif len(schedule[day][slot]) == 1:
                schedule[day][slot] = schedule[day][slot][0]
        elif schedule[day][slot].branch == branch:
            schedule[day][slot] = None

        class_slot = get_valid_assignment(schedule, courses, teachers, rooms, day, slot, branch)

        if class_slot:
            if schedule[day][slot] is None:
                schedule[day][slot] = class_slot
            elif isinstance(schedule[day][slot], list):
                schedule[day][slot].append(class_slot)
            else:
                schedule[day][slot] = [schedule[day][slot], class_slot]

    elif mutation_type == "swap":
        day1, slot1 = random.randint(0, DAYS - 1), random.randint(0, SLOTS_PER_DAY - 1)
        day2, slot2 = random.randint(0, DAYS - 1), random.randint(0, SLOTS_PER_DAY - 1)

        # Skip lunch slot
        if slot1 == LUNCH_SLOT or slot2 == LUNCH_SLOT:
            return

        # Skip empty slots
        if schedule[day1][slot1] is None or schedule[day2][slot2] is None:
            return

        # Handle swapping classes
        if isinstance(schedule[day1][slot1], list) and isinstance(schedule[day2][slot2], list):
            if len(schedule[day1][slot1]) > 0 and len(schedule[day2][slot2]) > 0:
                idx1 = random.randint(0, len(schedule[day1][slot1]) - 1)
                idx2 = random.randint(0, len(schedule[day2][slot2]) - 1)

                # Swap the classes
                schedule[day1][slot1][idx1], schedule[day2][slot2][idx2] = schedule[day2][slot2][idx2], \
                schedule[day1][slot1][idx1]

                # Update class day and slot info
                schedule[day1][slot1][idx1].day, schedule[day1][slot1][idx1].slot = day1, slot1
                schedule[day2][slot2][idx2].day, schedule[day2][slot2][idx2].slot = day2, slot2
        elif isinstance(schedule[day1][slot1], list) and not isinstance(schedule[day2][slot2], list):
            if len(schedule[day1][slot1]) > 0:
                idx = random.randint(0, len(schedule[day1][slot1]) - 1)
                schedule[day1][slot1][idx], schedule[day2][slot2] = schedule[day2][slot2], schedule[day1][slot1][idx]

                # Update class day and slot info
                schedule[day1][slot1][idx].day, schedule[day1][slot1][idx].slot = day1, slot1
                schedule[day2][slot2].day, schedule[day2][slot2].slot = day2, slot2
        elif not isinstance(schedule[day1][slot1], list) and isinstance(schedule[day2][slot2], list):
            if len(schedule[day2][slot2]) > 0:
                idx = random.randint(0, len(schedule[day2][slot2]) - 1)
                schedule[day1][slot1], schedule[day2][slot2][idx] = schedule[day2][slot2][idx], schedule[day1][slot1]

                # Update class day and slot info
                schedule[day1][slot1].day, schedule[day1][slot1].slot = day1, slot1
                schedule[day2][slot2][idx].day, schedule[day2][slot2][idx].slot = day2, slot2
        else:
            # Swap the classes
            schedule[day1][slot1], schedule[day2][slot2] = schedule[day2][slot2], schedule[day1][slot1]

            # Update class day and slot info
            schedule[day1][slot1].day, schedule[day1][slot1].slot = day1, slot1
            schedule[day2][slot2].day, schedule[day2][slot2].slot = day2, slot2

    elif mutation_type == "targeted":
        if not problem_courses:
            return  # No problems to fix

        problem_courses.sort(key=lambda x: x[3], reverse=True)
        course_teacher_counts = count_course_teacher_classes(schedule)

        teacher_course_problems = []
        for (course, teacher), count in course_teacher_counts.items():
            required = class_requirements.get(course, 1)
            if count != required:
                teacher_course_problems.append((course, teacher, count, required, abs(count - required)))

        teacher_course_problems.sort(key=lambda x: x[4], reverse=True)

        if teacher_course_problems:
            course_code, teacher_name, actual, required, diff = teacher_course_problems[0]
            course_details = next((c for c in courses if c[0] == course_code), None)
            if not course_details:
                return  # Course not found

            _, branch, course_name = course_details
        else:
            course_code, actual, required, diff = problem_courses[0]
            course_details = next((c for c in courses if c[0] == course_code), None)
            if not course_details:
                return  # Course not found

            _, branch, course_name = course_details
            teacher_name = None  # No specific teacher to target

        if actual < required:
            classes_to_add = required - actual
            for _ in range(classes_to_add):
                for attempt in range(20):
                    day, slot = random.randint(0, DAYS - 1), random.randint(0, SLOTS_PER_DAY - 1)

                    # Skip lunch slot
                    if slot == LUNCH_SLOT:
                        continue

                    # Check if slot is available
                    if schedule[day][slot] is not None:
                        if isinstance(schedule[day][slot], list) and len(schedule[day][slot]) >= MAX_CLASSES_PER_SLOT:
                            continue  # Slot is full

                    # Get a valid assignment
                    class_slot = get_valid_assignment(
                        schedule, courses, teachers, rooms, day, slot, branch,
                        course_teacher_counts=course_teacher_counts,
                        class_requirements=class_requirements,
                        specific_course=course_code,
                        specific_teacher=teacher_name
                    )

                    if class_slot and class_slot.course_code == course_code:
                        # Add to schedule
                        if schedule[day][slot] is None:
                            schedule[day][slot] = class_slot
                        elif isinstance(schedule[day][slot], list):
                            schedule[day][slot].append(class_slot)
                        else:
                            schedule[day][slot] = [schedule[day][slot], class_slot]
                        break  # Successfully added a class

        elif actual > required:
            classes_to_remove = actual - required

            # Find all slots with this course
            course_slots = []
            for day in range(DAYS):
                for slot in range(SLOTS_PER_DAY):
                    if slot == LUNCH_SLOT:
                        continue

                    if schedule[day][slot] is None:
                        continue

                    if isinstance(schedule[day][slot], list):
                        for i, class_data in enumerate(schedule[day][slot]):
                            if class_data is not None and class_data.course_code == course_code:
                                if teacher_name is None or class_data.teacher == teacher_name:
                                    course_slots.append((day, slot, i, class_data))
                    elif schedule[day][slot].course_code == course_code:
                        if teacher_name is None or schedule[day][slot].teacher == teacher_name:
                            course_slots.append((day, slot, None, schedule[day][slot]))

            # Sort and remove classes
            if teacher_name:
                course_slots.sort(key=lambda x: 0 if x[3].teacher == teacher_name else 1)
            else:
                random.shuffle(course_slots)

            removed_count = 0
            for day, slot, idx, class_data in course_slots:
                if removed_count >= classes_to_remove:
                    break

                if idx is None:
                    schedule[day][slot] = None
                else:
                    schedule[day][slot].pop(idx)
                    if not schedule[day][slot]:
                        schedule[day][slot] = None
                    elif len(schedule[day][slot]) == 1:
                        schedule[day][slot] = schedule[day][slot][0]

                removed_count += 1

    elif mutation_type == "multi":
        num_mutations = random.randint(2, 5)
        for _ in range(num_mutations):
            day, slot = random.randint(0, DAYS - 1), random.randint(0, SLOTS_PER_DAY - 1)

            if slot == LUNCH_SLOT:
                continue

            branch = random.choice(list(branches))
            if schedule[day][slot] is None:
                continue

            if isinstance(schedule[day][slot], list):
                schedule[day][slot] = [c for c in schedule[day][slot] if c is not None and c.branch != branch]
                if not schedule[day][slot]:
                    schedule[day][slot] = None
                elif len(schedule[day][slot]) == 1:
                    schedule[day][slot] = schedule[day][slot][0]
            elif schedule[day][slot].branch == branch:
                schedule[day][slot] = None

            class_slot = get_valid_assignment(schedule, courses, teachers, rooms, day, slot, branch)
            if class_slot:
                if schedule[day][slot] is None:
                    schedule[day][slot] = class_slot
                elif isinstance(schedule[day][slot], list):
                    schedule[day][slot].append(class_slot)
                else:
                    schedule[day][slot] = [schedule[day][slot], class_slot]


# The check_room_conflicts function has been consolidated at the top of the file
# The count_course_teacher_classes function has been consolidated and moved below
def count_classes_per_room(schedule):
    """Count how many classes are scheduled in each room.

    This helps us check if rooms are being used efficiently.
    """
    # Use a Counter to track room usage
    room_counts = Counter()

    # Go through each day and slot
    for day in range(DAYS):
        for slot in range(SLOTS_PER_DAY):
            # Skip lunch slot
            if slot == LUNCH_SLOT:
                continue

            # Skip empty slots
            if schedule[day][slot] is None:
                continue

            # Handle multiple classes in the same slot
            if isinstance(schedule[day][slot], list):
                for class_data in schedule[day][slot]:
                    # Skip None values
                    if class_data is None:
                        continue

                    # Get the room based on the type of class_data
                    room = class_data.room if hasattr(class_data, 'room') else class_data[3]
                    room_counts[room] += 1
            else:
                # Single class in this slot
                room = schedule[day][slot].room if hasattr(schedule[day][slot], 'room') else schedule[day][slot][3]
                room_counts[room] += 1

    return room_counts

def find_room_conflicts(schedule):
    """Find any conflicts where a room is used more than once in the same time slot.

    Returns a list of (day, slot, room) tuples where conflicts occur.
    """
    conflicts = []

    # Check each day and slot
    for day in range(DAYS):
        for slot in range(SLOTS_PER_DAY):
            # Skip lunch slot
            if slot == LUNCH_SLOT:
                continue

            # Skip empty slots
            if schedule[day][slot] is None:
                continue

            # Count rooms used in this slot
            room_counts = Counter()

            # Handle multiple classes in the same slot
            if isinstance(schedule[day][slot], list):
                for class_data in schedule[day][slot]:
                    if class_data is None:
                        continue

                    # Get room based on data type
                    room = class_data.room if hasattr(class_data, 'room') else class_data[3]
                    room_counts[room] += 1
            else:
                # Single class
                room = schedule[day][slot].room if hasattr(schedule[day][slot], 'room') else schedule[day][slot][3]
                room_counts[room] = 1

            # Add conflicts for any room used more than once
            for room, count in room_counts.items():
                if count > 1:
                    conflicts.append((day, slot, room))

    return conflicts

def count_course_classes(schedule):
    """Count the number of classes per course in the schedule.
    Optimized using Counter for faster counting operations.
    """
    # Pre-allocate a list to collect all course codes
    course_codes = []

    for day in range(DAYS):
        for slot in range(SLOTS_PER_DAY):
            if slot == LUNCH_SLOT:
                continue

            if not schedule[day][slot]:
                continue

            # Handle multiple classes in the same slot
            if isinstance(schedule[day][slot], list):
                for class_data in schedule[day][slot]:
                    if class_data is None:
                        continue

                    # Get course code
                    course_code = None
                    if hasattr(class_data, 'course_code'):
                        course_code = class_data.course_code
                    elif isinstance(class_data, tuple) and len(class_data) >= 7:
                        course_code = class_data[0]

                    if course_code and course_code != "LUNCH" and course_code != "EMPTY":
                        course_codes.append(course_code)
            else:
                # Single class
                course_code = None
                if hasattr(schedule[day][slot], 'course_code'):
                    course_code = schedule[day][slot].course_code
                elif isinstance(schedule[day][slot], tuple) and len(schedule[day][slot]) >= 7:
                    course_code = schedule[day][slot][0]

                if course_code and course_code != "LUNCH" and course_code != "EMPTY":
                    course_codes.append(course_code)

    # Count all course codes at once using Counter (more efficient than incrementing one by one)
    course_counter = Counter(course_codes)

    # Convert Counter to defaultdict for compatibility with existing code
    return defaultdict(int, course_counter)

def count_course_teacher_classes(schedule):
    """Count the number of classes per course-teacher pair in the schedule.

    This function goes through the entire schedule and counts how many classes
    each teacher is teaching for each course. It's optimized for performance
    and handles all possible schedule data formats.

    Args:
        schedule: The timetable schedule to check

    Returns:
        A defaultdict mapping (course_code, teacher) to the number of classes
    """
    # Handle None schedule case
    if schedule is None:
        return defaultdict(int)

    # Create a counter to keep track of course-teacher pairs
    course_teacher_counter = Counter()

    # Create a list to store all the course-teacher pairs we find
    # Using a list and then Counter.update() is more efficient than incrementing one by one
    course_teacher_pairs = []

    # Go through each day and slot in the schedule
    for day in range(DAYS):
        for slot in range(SLOTS_PER_DAY):
            # Skip lunch slot
            if slot == LUNCH_SLOT:
                continue

            # Skip empty slots
            if schedule[day][slot] is None:
                continue

            # Handle both single class and multiple classes in the same slot
            classes = schedule[day][slot] if isinstance(schedule[day][slot], list) else [schedule[day][slot]]

            for class_data in classes:
                # Skip None values
                if class_data is None:
                    continue

                # Extract course code and teacher based on the type of class_data
                if hasattr(class_data, 'course_code') and hasattr(class_data, 'teacher'):
                    # If it's a ClassSlot object
                    course_code = class_data.course_code
                    teacher = class_data.teacher
                elif isinstance(class_data, tuple) and len(class_data) >= 3:
                    # If it's a tuple (older format)
                    course_code = class_data[0]
                    teacher = class_data[2]  # Teacher is at index 2
                else:
                    # Skip invalid data
                    continue

                # Make sure we have valid data before adding to our count
                if course_code and teacher and course_code != "LUNCH" and course_code != "EMPTY":
                    # Add this pair to our list
                    course_teacher_pairs.append((course_code, teacher))

    # Count all pairs at once using Counter.update()
    # This is more efficient than incrementing one by one
    course_teacher_counter.update(course_teacher_pairs)

    # Convert Counter to defaultdict for compatibility with existing code
    # defaultdict will return 0 for any key that doesn't exist
    return defaultdict(int, course_teacher_counter)

def check_course_teacher_class_counts(schedule):
    """Check if each professor teaching a course has the correct number of classes for that course."""
    course_teacher_counts = count_course_teacher_classes(schedule)

    try:
        course_classes = get_course_classes()
        course_class_requirements = {}
        for course_code, num_classes, _, _ in course_classes:
            # Use the actual number of classes required from the database
            course_class_requirements[course_code] = int(num_classes)
    except:
        # If there's an error, use a default of 1 class per course
        course_class_requirements = defaultdict(lambda: 1)
    
    issues = []
    # Group by course_code to find all teachers for each course
    course_teachers = defaultdict(list)
    for (course_code, teacher), count in course_teacher_counts.items():
        course_teachers[course_code].append((teacher, count))
    
    # Check if each teacher has the correct number of classes for each course they teach
    for course_code, teachers in course_teachers.items():
        required_count = course_class_requirements.get(course_code, 2)  # Default to 2 if not found
        for teacher, count in teachers:
            if count != required_count:
                issues.append((course_code, teacher, count, required_count))
    
    # Get all course-teacher mappings from the database to ensure all professors have classes
    try:
        with sqlite3.connect("timetable.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.course_code, t.teacher_name, c.course_name
                FROM branch_teacher_courses btc
                JOIN courses c ON btc.course_code = c.course_code
                JOIN teachers t ON btc.teacher_id = t.teacher_id
            """)
            db_mappings = cursor.fetchall()
            
            # Check if all professors in the database have the required classes
            for course_code, teacher, _ in db_mappings:
                if course_code in course_class_requirements:
                    required_count = course_class_requirements[course_code]
                    actual_count = course_teacher_counts.get((course_code, teacher), 0)
                    
                    if actual_count != required_count:
                        # Only add if not already in issues
                        if not any(i[0] == course_code and i[1] == teacher for i in issues):
                            issues.append((course_code, teacher, actual_count, required_count))
    except sqlite3.Error as e:
        print(f"Database error when checking course-teacher mappings: {e}")
    
    return issues

def fitness(schedule):
    """Calculate the fitness of a timetable.

    This function evaluates how good a timetable is based on various constraints:

    Hard Constraints (High Penalty):
    1. No teacher should teach multiple classes at the same time
    2. No room should be used for multiple classes at the same time
    3. No branch should have multiple classes at the same time
    4. Each professor should have the required number of classes for each course they teach
    5. Each course should have the required number of classes per week

    Soft Constraints (Higher Emphasis):
    6. Avoid more than 3 consecutive classes for same branch without breaks (exponential penalty)
    7. Avoid more than 3 consecutive classes for same teacher without breaks (higher exponential penalty)
    8. Ensure even distribution of teacher workload across different days (variance-based penalty)
    9. Prefer core courses to be scheduled in morning slots (significant bonus)
    10. Encourage balanced distribution of classes within each day (rewards coverage, penalizes clumping)
    11. Prefer balanced distribution of classes across the week for both branches and teachers
    12. Encourage teacher diversity (teachers teaching multiple courses)
    """
    if not schedule:
        return 0

    # Start with a much higher base score to avoid negative values
    score = 5000.0
    conflict_count = 0

    # Get course class requirements with reduced values to ease constraints
    try:
        course_classes = get_course_classes()
        class_requirements = {}
        for course_code, num_classes, _, _ in course_classes:
            # Use the actual number of classes required from the database
            class_requirements[course_code] = int(num_classes)
    except:
        # If there's an error, use a default of 1 class per course
        class_requirements = defaultdict(lambda: 1)

    # Use a Counter for efficient counting
    from collections import Counter
    course_teacher_counts = Counter()
    course_counts = Counter()  # Track total classes per course

    # Track classes per day for each branch and teacher
    branch_day_counts = defaultdict(lambda: defaultdict(int))  # {branch: {day: count}}
    teacher_day_counts = defaultdict(lambda: defaultdict(int))  # {teacher: {day: count}}

    # Track branch and teacher classes by day and slot for consecutive class check
    branch_slots = {}  # {branch: {day: [slots with classes]}}
    teacher_slots = {}  # {teacher: {day: [slots with classes]}}

    # Check for conflicts in each slot
    for day in range(DAYS):
        for slot in range(SLOTS_PER_DAY):
            if slot == LUNCH_SLOT:
                continue

            if not schedule[day][slot]:
                continue

            # Check for conflicts in this slot
            teachers_used = set()
            rooms_used = set()
            branches_used = set()

            # Handle multiple classes in the same slot
            classes = schedule[day][slot] if isinstance(schedule[day][slot], list) else [schedule[day][slot]]

            for class_data in classes:
                if class_data is None:
                    continue

                # Extract data
                if hasattr(class_data, 'course_code'):
                    course_code = class_data.course_code
                    teacher = class_data.teacher
                    room = class_data.room
                    branch = class_data.branch
                else:
                    course_code = class_data[0]
                    teacher = class_data[2]
                    room = class_data[3]
                    branch = class_data[4]

                # Count classes
                course_counts[course_code] += 1
                course_teacher_counts[(course_code, teacher)] += 1

                # Track classes per day
                branch_day_counts[branch][day] += 1
                teacher_day_counts[teacher][day] += 1

                # Track branch slots for consecutive class check
                if branch not in branch_slots:
                    branch_slots[branch] = {}
                if day not in branch_slots[branch]:
                    branch_slots[branch][day] = []
                branch_slots[branch][day].append(slot)
                
                # Track teacher slots for consecutive class check
                if teacher not in teacher_slots:
                    teacher_slots[teacher] = {}
                if day not in teacher_slots[teacher]:
                    teacher_slots[teacher][day] = []
                teacher_slots[teacher][day].append(slot)

                # Check for conflicts - with reduced penalties
                if teacher in teachers_used:
                    score -= 10.0  # Reduced penalty for teacher conflicts
                    conflict_count += 1
                teachers_used.add(teacher)

                if room in rooms_used:
                    score -= 10.0  # Reduced penalty for room conflicts
                    conflict_count += 1
                rooms_used.add(room)

                if branch in branches_used:
                    score -= 5.0  # Reduced penalty for branch conflicts
                    conflict_count += 1
                branches_used.add(branch)

            # Add a small bonus for each class scheduled (to encourage filling the timetable)
            score += len(classes) * 2.0
            
            # Add bonus for core courses scheduled in preferred morning slots
            for class_data in classes:
                if class_data is None:
                    continue
                    
                course_code = class_data.course_code if hasattr(class_data, 'course_code') else class_data[0]
                
                # Check if this is a core course in a preferred morning slot
                if course_code in CORE_COURSES and slot in PREFERRED_MORNING_SLOTS:
                    # Significant bonus for scheduling core courses in the morning
                    score += 10.0

    # Check for consecutive classes for each branch
    for branch, days in branch_slots.items():
        for day, slots in days.items():
            # Sort slots to check for consecutive ones
            slots.sort()

            # Check for consecutive slots
            consecutive_count = 1
            for i in range(1, len(slots)):
                # If slots are consecutive (accounting for lunch break)
                if slots[i] == slots[i-1] + 1 or (slots[i-1] < LUNCH_SLOT and slots[i] > LUNCH_SLOT and slots[i] == slots[i-1] + 2):
                    consecutive_count += 1
                else:
                    consecutive_count = 1

                # Penalize if more than 3 consecutive classes
                if consecutive_count > 3:
                    # Apply a stronger soft penalty for each additional consecutive class
                    # Exponential penalty to heavily discourage long consecutive stretches
                    penalty = 10.0 * (consecutive_count - 3) ** 2
                    score -= penalty
    
    # Check for consecutive classes for each teacher
    for teacher, days in teacher_slots.items():
        for day, slots in days.items():
            # Sort slots to check for consecutive ones
            slots.sort()

            # Check for consecutive slots
            consecutive_count = 1
            for i in range(1, len(slots)):
                # If slots are consecutive (accounting for lunch break)
                if slots[i] == slots[i-1] + 1 or (slots[i-1] < LUNCH_SLOT and slots[i] > LUNCH_SLOT and slots[i] == slots[i-1] + 2):
                    consecutive_count += 1
                else:
                    consecutive_count = 1

                # Penalize if more than 3 consecutive classes for a teacher
                if consecutive_count > 3:
                    # Exponential penalty with higher weight for teachers to prioritize teacher breaks
                    penalty = 15.0 * (consecutive_count - 3) ** 2
                    score -= penalty
                    conflict_count += 1

    # Check for even distribution of teacher workload across days
    for teacher, day_counts in teacher_day_counts.items():
        if len(day_counts) > 1:  # Only check if teacher teaches on multiple days
            # Calculate average and standard deviation of classes per day
            days_with_classes = len(day_counts)
            total_classes = sum(day_counts.values())
            avg_classes_per_day = total_classes / days_with_classes
            
            # Calculate variance (average squared deviation)
            variance = sum((count - avg_classes_per_day) ** 2 for count in day_counts.values()) / days_with_classes
            
            # Penalize uneven distribution - higher variance means more uneven distribution
            score -= 12.0 * (variance ** 0.5)
    
    # Check if each course has the required number of classes
    for course_code, count in course_counts.items():
        required = class_requirements.get(course_code, 1)
        if count != required:
            # Penalize for each missing or extra class
            score -= 20.0 * abs(count - required)

    # Check if each teacher has the required number of classes for each course
    for (course_code, teacher), count in course_teacher_counts.items():
        required = class_requirements.get(course_code, 1)
        if count != required:
            # Penalize for each missing or extra class
            score -= 15.0 * abs(count - required)

    # Check for balanced distribution of classes within each day for each branch
    for branch, day_data in branch_slots.items():
        for day, slots in day_data.items():
            # Skip days with few classes
            if len(slots) < 3:
                continue
                
            # Calculate how spread out the classes are throughout the day
            slots.sort()
            total_slots = SLOTS_PER_DAY - 1  # Excluding lunch
            coverage = len(slots) / total_slots  # What percentage of the day is used
            
            # Calculate average gap between classes
            if len(slots) > 1:
                gaps = [slots[i] - slots[i-1] for i in range(1, len(slots))]
                avg_gap = sum(gaps) / len(gaps)
                gap_variance = sum((gap - avg_gap) ** 2 for gap in gaps) / len(gaps)
                
                # Reward consistent gaps (low variance) and good coverage
                score += 8.0 * coverage  # Reward using more of the day
                score -= 6.0 * (gap_variance ** 0.5)  # Penalize uneven gaps
    
    teacher_courses = defaultdict(set)
    for (course_code, teacher) in course_teacher_counts:
        teacher_courses[teacher].add(course_code)

    for teacher, courses in teacher_courses.items():
        if len(courses) > 1:
            score += len(courses) * 15.0  # Increased bonus for each additional course a teacher teaches

    return max(0, score)  # Ensure fitness is never negative


def validate_schedule(schedule, fitness_score):
    if fitness_score < 4500:
        return False

    if find_room_conflicts(schedule):  
        return False

    course_counts = defaultdict(int)
    course_teacher_counts = defaultdict(int)

    for day in range(DAYS):
        for slot in range(SLOTS_PER_DAY):
            if slot == LUNCH_SLOT or schedule[day][slot] is None:
                continue

            classes = schedule[day][slot] if isinstance(schedule[day][slot], list) else [schedule[day][slot]]
            for class_obj in classes:
                if not class_obj:
                    continue

                if isinstance(class_obj, tuple) and len(class_obj) >= 3:
                    course_code, teacher = class_obj[0], class_obj[2]
                else:
                    course_code = getattr(class_obj, 'course_code', None)
                    teacher = getattr(class_obj, 'teacher', None)

                if course_code and course_code not in ("LUNCH", "EMPTY"):
                    course_counts[course_code] += 1
                    if teacher:
                        course_teacher_counts[(course_code, teacher)] += 1

    class_requirements = {
        course_code: int(num_classes)
        for course_code, num_classes, _, _ in get_course_classes()
    }

    for course_code, required in class_requirements.items():
        if course_counts[course_code] != required:
            return False

    for (course_code, teacher), count in course_teacher_counts.items():
        if count != class_requirements.get(course_code, 2):
            return False

    try:
        with sqlite3.connect("timetable.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.course_code, t.teacher_name
                FROM branch_teacher_courses btc
                JOIN courses c ON btc.course_code = c.course_code
                JOIN teachers t ON btc.teacher_id = t.teacher_id
            """)
            db_mappings = cursor.fetchall()

            for course_code, teacher in db_mappings:
                required = class_requirements.get(course_code, 0)
                actual = course_teacher_counts.get((course_code, teacher), 0)
                if actual != required:
                    return False
    except sqlite3.Error as e:
        print(f"Database error during validation: {e}")
        return False

    return True


def genetic_algorithm(branches=None, generations=100, verbose=True):
    start_time = time.time()

    courses, teachers, rooms = fetch_data_from_db()

    if verbose:
        print(f"Loaded {len(courses)} courses, {len(teachers)} teachers, and {len(rooms)} rooms")
        print("Generating high-quality initial population with constraint-based scheduling...")

    if not branches:
        branches = {course[1] for course in courses}

    if branches and not isinstance(branches, set):
        branches = set(branches)
        courses = [course for course in courses if course[1] in branches]

    candidate_schedules = []
    best_initial_schedule = None
    best_initial_fitness = -1
    num_candidates = POPULATION_SIZE

    for attempt in range(num_candidates):
        if verbose:
            print(f"Generating candidate schedule {attempt + 1}/{num_candidates}...")

        initial_schedule = create_random_schedule(courses, teachers, rooms)
        if initial_schedule is None:
            continue

        initial_fitness = fitness(initial_schedule)
        candidate_schedules.append((initial_schedule, initial_fitness))

        if initial_fitness > best_initial_fitness:
            best_initial_schedule = copy_schedule(initial_schedule)
            best_initial_fitness = initial_fitness
            if verbose:
                print(f"New best initial schedule: fitness = {best_initial_fitness:.2f}")

        if initial_fitness > 4000:
            if verbose:
                print(f"Found excellent initial schedule with fitness {initial_fitness:.2f}")
            break

    candidate_schedules.sort(key=lambda x: x[1], reverse=True)
    population = [best_initial_schedule] if best_initial_schedule else []

    for schedule, _ in candidate_schedules:
        if len(population) < POPULATION_SIZE and schedule != best_initial_schedule:
            population.append(schedule)

    while len(population) < POPULATION_SIZE:
        schedule = create_random_schedule(courses, teachers, rooms)
        if schedule:
            population.append(schedule)

    if verbose:
        print(f"Initial population created with {len(population)} schedules.")
        print(f"Best initial fitness: {best_initial_fitness:.2f}")

    population.sort(key=lambda x: fitness(x), reverse=True)
    best_schedule = copy_schedule(population[0])
    best_fitness = fitness(best_schedule)

    if verbose:
        print(f"Initial best fitness: {best_fitness:.2f}")

    for generation in range(generations):
        new_population = []

        for i in range(ELITE_SIZE):
            new_population.append(copy_schedule(population[i]))

        while len(new_population) < POPULATION_SIZE:
            parent1 = tournament_selection(population)
            parent2 = tournament_selection(population)

            if random.random() < CROSSOVER_RATE:
                child = crossover(parent1, parent2, courses, teachers, rooms)
            else:
                child = copy_schedule(parent1 if random.random() < 0.5 else parent2)

            if random.random() < MUTATION_RATE:
                mutate(child, courses, teachers, rooms)

            new_population.append(child)

        population = new_population
        population.sort(key=lambda x: fitness(x), reverse=True)

        current_best_fitness = fitness(population[0])
        if current_best_fitness > best_fitness:
            best_schedule = copy_schedule(population[0])
            best_fitness = current_best_fitness
            if verbose and generation % 5 == 0:
                print(f"Generation {generation}: New best fitness: {best_fitness:.2f}")

        if best_schedule and best_fitness >= 4500:
            if validate_schedule(best_schedule, best_fitness):
                print(f"Generation {generation}: Found optimal solution with fitness {best_fitness:.2f}")
                break

    # Final evaluation
    if best_schedule is None:
        print("\nFailed to generate a valid schedule.")
        return None, None

    conflicts = check_room_conflicts(best_schedule)
    print(f"\nGenetic algorithm completed in {time.time() - start_time:.2f} seconds")
    print(f"Best fitness: {best_fitness:.2f}")
    print(f"Room conflicts: {len(conflicts) if conflicts else 0}")

    course_teacher_issues = check_course_teacher_class_counts(best_schedule)
    print(f"Course-teacher class count issues: {len(course_teacher_issues)}")
    print_course_teacher_counts(best_schedule)

    if len(course_teacher_issues) > 0:
        print("\nApplying post-processing to fix class assignments...")
        fixed_schedule = fix_class_assignments(best_schedule, courses, teachers, rooms)
        fixed_issues = check_course_teacher_class_counts(fixed_schedule)
        if len(fixed_issues) < len(course_teacher_issues):
            print(f"Fixed schedule reduced issues from {len(course_teacher_issues)} to {len(fixed_issues)}")
            best_schedule = fixed_schedule

    professor_schedules = create_professor_schedules(best_schedule)
    print("Timetable generated successfully! Ready for database insertion.")

    return best_schedule, professor_schedules





def create_professor_schedules(schedule):
    """Create a dictionary of professor schedules from the timetable using ClassSlot objects."""
    professor_schedules = {}

    # Process each slot in the schedule
    for day in range(DAYS):
        for slot in range(SLOTS_PER_DAY):
            if slot == LUNCH_SLOT or schedule[day][slot] is None:
                continue

            # Handle both list and single class cases
            classes = schedule[day][slot] if isinstance(schedule[day][slot], list) else [schedule[day][slot]]

            for class_data in classes:
                if class_data is None:
                    continue

                # Convert to ClassSlot if it's not already
                if not isinstance(class_data, ClassSlot):
                    # Extract data from tuple
                    if len(class_data) >= 7:
                        course_code = class_data[0]
                        course_name = class_data[2] if len(class_data) > 2 else ""
                        teacher = class_data[2]
                        room = class_data[3]
                        branch = class_data[4]
                        class_day = class_data[5]
                        class_slot = class_data[6]

                        # Create ClassSlot object
                        class_data = ClassSlot(course_code, course_name, teacher, room, branch, class_day, class_slot)
                    else:
                        # Skip invalid data
                        continue

                # Get data from ClassSlot object
                teacher = class_data.teacher

                # Initialize professor schedule if not exists
                if teacher not in professor_schedules:
                    professor_schedules[teacher] = {}

                # Add class to professor schedule using day/slot as key
                professor_schedules[teacher][(day, slot)] = class_data
    
    return professor_schedules

def print_timetable(schedule, file=None):
    """Print the timetable in a readable format.

    Args:
        schedule: The timetable schedule to print
        file: Optional file-like object to print to (defaults to sys.stdout)
    """
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    time_slots = [
        "8:00 - 9:00", "9:00 - 10:00", "10:00 - 11:00", "11:00 - 12:00",
        "12:00 - 1:00", "1:00 - 2:00", "2:00 - 3:00", "3:00 - 4:00", "4:00 - 5:00"
    ]

    print("\n=== TIMETABLE ===\n", file=file)

    # Create a table for each day
    for day_idx, day in enumerate(days):
        print(f"\n=== {day} ===\n", file=file)

        table_data = []
        for slot_idx, time_slot in enumerate(time_slots):
            row = [time_slot]

            if slot_idx == LUNCH_SLOT:
                row.append("LUNCH BREAK")
            elif schedule[day_idx][slot_idx] is None:
                row.append("---")
            else:
                if isinstance(schedule[day_idx][slot_idx], list):
                    classes = []
                    for class_data in schedule[day_idx][slot_idx]:
                        if class_data is None:
                            continue

                        if hasattr(class_data, 'course_code'):
                            class_str = f"{class_data.course_code}: {class_data.course_name}\nTeacher: {class_data.teacher}\nRoom: {class_data.room}\nBranch: {class_data.branch}"
                        else:
                            course_code, _, course_name, teacher, room, branch, _, _ = class_data
                            class_str = f"{course_code}: {course_name}\nTeacher: {teacher}\nRoom: {room}\nBranch: {branch}"

                        classes.append(class_str)

                    row.append("\n\n".join(classes) if classes else "---")
                else:
                    class_data = schedule[day_idx][slot_idx]

                    if hasattr(class_data, 'course_code'):
                        class_str = f"{class_data.course_code}: {class_data.course_name}\nTeacher: {class_data.teacher}\nRoom: {class_data.room}\nBranch: {class_data.branch}"
                    else:
                        course_code, _, course_name, teacher, room, branch, _, _ = class_data
                        class_str = f"{course_code}: {course_name}\nTeacher: {teacher}\nRoom: {room}\nBranch: {branch}"

                    row.append(class_str)

            table_data.append(row)

        print(tabulate(table_data, headers=["Time", "Class"], tablefmt="grid"), file=file)

def print_professor_schedules(professor_schedules, file=None):
    """Print schedules for all professors.

    Args:
        professor_schedules: Dictionary of professor schedules where keys are (day, slot) tuples
        file: Optional file-like object to print to (defaults to sys.stdout)
    """
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    time_slots = [
        "8:00 - 9:00", "9:00 - 10:00", "10:00 - 11:00", "11:00 - 12:00",
        "12:00 - 1:00", "1:00 - 2:00", "2:00 - 3:00", "3:00 - 4:00", "4:00 - 5:00"
    ]

    print("\n=== PROFESSOR SCHEDULES ===\n", file=file)

    for professor, schedule in sorted(professor_schedules.items()):
        print(f"\n=== Schedule for Professor: {professor} ===\n", file=file)

        table_data = []
        for day_idx, day in enumerate(days):
            row = [day]
            for slot_idx in range(len(time_slots)):
                if slot_idx == LUNCH_SLOT:
                    row.append("LUNCH")
                elif (day_idx, slot_idx) in schedule:
                    class_info = schedule[(day_idx, slot_idx)]
                    
                    # Handle different class_info formats
                    if hasattr(class_info, 'course_code'):
                        cell = f"{class_info.course_code}: {class_info.course_name}\nRoom: {class_info.room}\nBranch: {class_info.branch}"
                    elif isinstance(class_info, dict):
                        cell = f"{class_info['course_code']}: {class_info['course_name']}\nRoom: {class_info['room']}\nBranch: {class_info['branch']}"
                    else:
                        # Assume it's a tuple
                        try:
                            course_code, _, course_name, teacher, room, branch, _, _ = class_info
                            cell = f"{course_code}: {course_name}\nRoom: {room}\nBranch: {branch}"
                        except:
                            # Fallback for unknown format
                            cell = str(class_info)
                    
                    row.append(cell)
                else:
                    row.append("---")
            table_data.append(row)

        headers = ["Day"] + time_slots
        print(tabulate(table_data, headers=headers, tablefmt="grid"), file=file)

def print_course_teacher_counts(schedule):
    """Print the number of classes per course-teacher pair in the schedule."""
    course_teacher_counts = count_course_teacher_classes(schedule)
    
    try:
        course_class_requirements = {course_code: num_classes for course_code, num_classes, _, _ in get_course_classes()}
    except:
        # If there's an error, use a default of 2 classes per course
        course_class_requirements = defaultdict(lambda: 2)
    
    # Get all course-teacher mappings from the database
    db_mappings = []
    try:
        with sqlite3.connect("timetable.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.course_code, t.teacher_name, c.course_name
                FROM branch_teacher_courses btc
                JOIN courses c ON btc.course_code = c.course_code
                JOIN teachers t ON btc.teacher_id = t.teacher_id
            """)
            db_mappings = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database error when fetching course-teacher mappings: {e}")
    
    print("\n=== COURSE-TEACHER CLASS COUNTS ===\n")
    
    table_data = []
    
    # First add all mappings from the schedule
    course_teachers = defaultdict(list)
    for (course_code, teacher), count in course_teacher_counts.items():
        course_teachers[course_code].append((teacher, count))
    
    for course_code, teachers in sorted(course_teachers.items()):
        required = course_class_requirements.get(course_code, 2)
        
        for teacher, count in sorted(teachers):
            table_data.append([course_code, teacher, count, required, ""])
    
    # Then add any missing mappings from the database
    for course_code, teacher, _ in db_mappings:
        if course_code in course_class_requirements:
            # Skip if already in table_data
            if any(row[0] == course_code and row[1] == teacher for row in table_data):
                continue
                
            required = course_class_requirements[course_code]
            count = 0  # Not in schedule
            table_data.append([course_code, teacher, count, required, ""])
    
    headers = ["Course", "Teacher", "Actual Classes", "Required Classes", "Status"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    # Print summary
    correct_count = sum(1 for row in table_data if row[2] == row[3])
    total_count = len(table_data)
    if total_count > 0:
        print(f"\nCorrect course-teacher pairs: {correct_count}/{total_count} ({correct_count/total_count*100:.1f}%)")
    else:
        print("\nNo course-teacher pairs found.")
    
    # Check if all requirements are met
    if correct_count == total_count and total_count > 0:
        print("All professors have the correct number of classes for each course they teach!")
    else:
        print("Some professors don't have the correct number of classes for their courses.")