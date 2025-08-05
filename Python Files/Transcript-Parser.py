# Ethan Otero, 3/15/25
# This code has so far been flawless at parsing through transcripts; I hope to see it continue this streak with a larger dataset. 
# Due to the fact that students are anonymous, there's no way to tell if there are duplicate records for the same student. As such, it's advised to only run this py file once per pdf.

import PyPDF2 as p2
import sqlite3

from Startup import DB

PDF_FILE = "G:\Downloads\GrAI\Test Sample 2 AS for Dotnet_Redacted Two-Column_Redacted.pdf" # if you plan on running this, change the filename to match your PDF
connection_obj = sqlite3.connect(DB)
cursor = connection_obj.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS students (student_id, program STRING)")
cursor.execute("CREATE TABLE IF NOT EXISTS enrollments (student_id, code STRING, grade STRING, FOREIGN KEY (student_id) REFERENCES students(student_id), FOREIGN KEY (code) REFERENCES courses(code))")
pdfFile = open(PDF_FILE, 'rb')
pdfread = p2.PdfReader(pdfFile)

def group_pages(pages):
    """
    Group a list (in this case, of pdf pages) into pairs.
    
    Args:
        pages: pages to group
    Returns:
        pair_pages: paired list of pages
    """
    pair_pages = list(zip(pages[::2], pages[1::2]))
    return pair_pages

cursor.execute("SELECT code FROM courses")
course_code_list = cursor.fetchall()
cliffs_exist = False

page_list = group_pages(pdfread.pages)
cursor.execute("SELECT student_id FROM students ORDER BY student_id DESC") # Gets the last Student ID used (to prevent collisions)
student_id = cursor.fetchone()
try:
    student_id = student_id[0]
except:
    student_id = 0
for pair in page_list:
    cliffs_exist = False
    student_id += 1
    print(f"STUDENT {student_id}:")
    
    page1_raw_text = pair[0].extract_text() # Extracts raw text from first page
    page2_raw_text = pair[1].extract_text() # Extracts raw text from second page

    start_program_index = page1_raw_text.find("Program:") # Finds the Program of Study
    start_program_index+= len("Program: ")
    end_program_index = page1_raw_text.find("(", start_program_index)
    program = page1_raw_text[start_program_index:end_program_index]
    print(program)
    cursor.execute("INSERT INTO students (student_id, program) VALUES (?,?)", (student_id, program,))
    course_cavern_start = page2_raw_text.find("OTHER COURSES:") # Finds "Other Courses"
    course_cavern_start += len("OTHER COURSES:")
    course_cavern_end = page2_raw_text.find("=================================================================", course_cavern_start)

    if course_cavern_end == -1: # Detects if "Other Courses" wrapped around, and if so, plans accordingly
        cliffs_exist = True
        course_cliff_start = page2_raw_text.find("----------------------------------------------------------------------------------------------------------------------------------")
        course_cliff_start += len("----------------------------------------------------------------------------------------------------------------------------------")
        course_cliff_end = page2_raw_text.find("=================================================================", course_cliff_start)
    
    course_caverns = page2_raw_text[course_cavern_start:course_cavern_end] # Sets a value for the "Other Courses" section

    if cliffs_exist:
        course_cliffs = page2_raw_text[course_cliff_start:course_cliff_end] # Sets a value for the wrapped "Other Courses" section (if it exists)
    for code in course_code_list: # Iterates through every course code ever
        code = code[0]
        spaced_code = f"       {code}" # Detects courses in main course section
        dotted_code = f"{code}..." # Detects courses in "Other Courses" section

        if spaced_code in page1_raw_text: # Check for the specially formatted course code in main courses
            start_course_index = page1_raw_text.find(spaced_code)
            start_course_index+= len(spaced_code)
            start_grade_index = start_course_index + 35 - len(code)
            end_grade_index = start_grade_index + 1
            print(f"{code}: Page 1")
            grade = page1_raw_text[start_grade_index:end_grade_index]
            if grade == "T":
                grade = "TR"
            if grade == "_" or grade == " ":
                grade = None
            print(grade)
            cursor.execute("INSERT INTO enrollments (student_id, code, grade) VALUES (?,?,?)", (student_id, code, grade))

        if spaced_code in page2_raw_text: # Check for the specially formatted course code in main courses
            start_course_index = page2_raw_text.find(spaced_code)
            start_course_index+= len(spaced_code)
            start_grade_index = start_course_index + 35 - len(code)
            end_grade_index = start_grade_index + 1
            print(f"{code}: Page 2")
            grade = page2_raw_text[start_grade_index:end_grade_index]

            if grade == "T":
                grade = "TR"
            if grade == "_" or grade == " ":
                grade = None
            
            print(grade)
            cursor.execute("INSERT INTO enrollments (student_id, code, grade) VALUES (?,?,?)", (student_id, code, grade))

        if dotted_code in course_caverns: # Check for the specially formatted course code in "Other Courses"

            start_course_index = course_caverns.find(dotted_code)
            start_course_index+= len(code)
            start_grade_index = start_course_index + 30 - len(code)
            end_grade_index = start_grade_index + 1
            grade = course_caverns[start_grade_index:end_grade_index]
            print(f"{code}: Course Caverns")
            print(grade)
            if grade == "T":
                grade = "TR"
            if grade == "_" or grade == " ":
                grade = None
            cursor.execute("INSERT INTO enrollments (student_id, code, grade) VALUES (?,?,?)", (student_id, code, grade))

        if cliffs_exist: # If the text wraps around, 
            if dotted_code in course_cliffs: # Check for the specially formatted course code
                start_course_index = course_cliffs.find(dotted_code)
                start_course_index+= len(code)
                start_grade_index = start_course_index + 30 - len(code)
                end_grade_index = start_grade_index + 1
                grade = course_cliffs[start_grade_index:end_grade_index]
                if grade == "T":
                    grade = "TR"
                if grade == "_" or grade == " ":
                    grade = None
                print(f"{code}: Course Cliffs")
                print(grade)
                cursor.execute("INSERT INTO enrollments (student_id, code, grade) VALUES (?,?,?)", (student_id, code, grade))

connection_obj.commit() # Commits changes to the SQL database
