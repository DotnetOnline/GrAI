# Ethan Otero, 5/1/25
# This code accepts a student transcript, and outputs a predicted grade.
# Thank you so much for helping me through this process!!

import sqlite3
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import pandas as pd
import numpy as np
import PyPDF2 as p2

from Startup import DB, STUDENT_TRANSCRIPT


connection_obj = sqlite3.connect(DB)
cursor = connection_obj.cursor()

grade_mapping = {'A': 4.0, 'B': 3.0, 'C': 2.0, 'D': 1.0, 'F': 0.0}
gpa_mapping = {4: 'A', 3: 'B', 2: 'C', 1: 'D', 0: 'F'}
courses = pd.read_sql_query("SELECT coid, code, title FROM courses", connection_obj)
enrollments = pd.read_sql_query("SELECT student_id, code, grade, cluster_number FROM enrollments_with_clusters", connection_obj)

print(f"SQL table loaded. Currently contains: {len(courses)} courses.")

model = SentenceTransformer('all-mpnet-base-v2')
embeddings = model.encode(courses['title'].tolist())

n_clusters = 15
kmeans = KMeans(n_clusters=n_clusters, random_state=42)
labels = kmeans.fit_predict(embeddings)

courses['cluster_number'] = labels

courses['cluster_name'] = ''
courses['notes'] = ''

courses.to_sql('courses_with_clusters', connection_obj, if_exists='replace', index=False)

print("Clustered courses written back into the database under 'courses_with_clusters'.")

# grade cleanup (removes transfers/non-completion, and maps letter grades to GPA values)
enrollments = enrollments[enrollments['grade'].notna() & (enrollments['grade'].str.upper() != 'TR')] 
enrollments['grade'] = enrollments['grade'].map(grade_mapping)
enrollments = enrollments.dropna(subset=['grade'])

student_cluster_avg = enrollments.groupby(['student_id', 'cluster_number'])['grade'].mean().unstack(fill_value=np.nan)
student_cluster_avg.columns = [f'cluster_{int(col)}_average_grade' for col in student_cluster_avg.columns]



overall_gpa = enrollments.groupby('student_id')['grade'].mean().rename('GPA')

data = student_cluster_avg.merge(overall_gpa, on='student_id')
examples = []

for idx, enrollment in enrollments.iterrows():
    student_id = enrollment['student_id']
    course_cluster = enrollment['cluster_number']
    grade = enrollment['grade']

    if pd.isna(grade) or student_id not in data.index:
        continue

    features = []
    for c in range(12):  # 12 clusters
        if f'cluster_{c}_average_grade' in data.columns:
            val = data.loc[student_id, f'cluster_{c}_average_grade']
            if np.isnan(val):
                val = data.loc[student_id, 'GPA']  # fallback to GPA if no data
        else:
            val = data.loc[student_id, 'GPA']
        features.append(val)
    for c in range(12):
        features.append(1 if c == course_cluster else 0)
    
    examples.append((features, grade))

print(examples)

X = pd.DataFrame([ex[0] for ex in examples])
y = pd.Series([ex[1] for ex in examples]).dropna()

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=141)

model = RandomForestRegressor(n_estimators=1000, random_state=141)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)


def predict_student_grade(student_courses, course_cluster, cluster_count=12):
    """
    Predict a student's grade, given a list of courses they've taken.
    Args:
        student_courses: list of tuples (CourseCode, Grade)
        course_cluster: cluster_id of the target course
    Returns:
        prediction: the model's prediction of how the student will perform
    """
    # create cluster averages
    cluster_grades = {c: [] for c in range(cluster_count)}
    for code, grade in student_courses:
        cluster = course_to_cluster(code)
        cluster_grades[cluster].append(grade)

    features = []
    all_grades = [g for grades in cluster_grades.values() for g in grades]
    overall_gpa = np.mean(all_grades) if all_grades else 3.0
    for c in range(cluster_count):
        grades = cluster_grades[c]
        if grades:
            features.append(np.mean(grades))
        else:
            features.append(overall_gpa)

    for c in range(cluster_count):
        features.append(1 if c == course_cluster else 0)
    
    prediction = model.predict([features])[0]
    return prediction

student_courses = []

def append_course(code, grade):
    """
    Appends courses and mapped grades to the full list of student courses, filtering out any that aren't relevant (in-progress/transferred without grade)
    Args:
        code (str): code to be appended
        grade (str): grade to be appended
    """
    if grade == None:
        print(f"Skipping course: {code} (Reason: in-progress or incomplete)")
    elif grade == "T":
        print(f"Skipping course: {code} (Reason: Transferred without grade)")
    elif grade == "W":
        print(f"Skipping course: {code} (Reason: Withdrawn)")
    else:
        mapped_grade = grade_mapping[grade]
        student_tuple = (code,mapped_grade)
        student_courses.append(student_tuple)

def scrape_courses(section, page_num):
    """
    Sends courses/grades in a given section of text to be appended.

    Args:
        section (str): Text to look through
    """
    cursor.execute("SELECT code FROM courses")
    course_code_list = cursor.fetchall()
    for code in course_code_list: # iterates through every course code ever
        code = code[0]
        if code in section:
            start_course_index = section.find(code)
            start_course_index+= len(code)
            start_grade_index = start_course_index + 42 - len(code)
            end_grade_index = start_grade_index + 1
            grade = section[start_grade_index:end_grade_index]
            if grade == "T":
                grade = "TR"
            if grade == "_" or grade == " ":
                grade = None
            append_course(code,grade)

def transcript_scraper(transcript):
    """
    Find all instances of courses (and their respective grades) from an unofficial transcript.
    
    Args:
        transcript (string): Path to a student's transcript file
        
    Returns:
        student_courses (tuple): Courses a student is taking, along with their respective grades
        """
    transcript_file = open(transcript, 'rb')
    transcript_read = p2.PdfReader(transcript_file)
    
    page_list = transcript_read.pages

    print(f"BEGINNING TRANSCRIPT EXTRACTION:")

    page_num = 1
    for page in page_list:
        page_raw_text = page.extract_text()
        current_section = page_raw_text[:]
        semesters = page_raw_text.count("Semester")
        for i in range (0,semesters):
            courses_start = current_section.find("Semester")
            courses_end = current_section.find("Cumulative Totals:")
            section = current_section[courses_start:courses_end]
            if courses_start > courses_end:
                print("ERROR: Improper formatting")
                print(current_section[courses_end:])
            scrape_courses(section,page_num)
            next_section_start = courses_end + len("Cumulative Totals:")
            current_section = current_section[next_section_start:]
        page_num+=1

    return student_courses

def course_to_cluster(code):
    """
    Convert a course code into its respective cluster.
    Args:
        code (str): course code
    Returns:
        cluster (int): cluster number for the course
    """
    cursor.execute("SELECT cluster_number FROM courses_with_clusters WHERE code = ?", (code,))
    result = cursor.fetchone()
    cluster = result[0]
    return cluster

student_courses = transcript_scraper(STUDENT_TRANSCRIPT)
print(f"\n\n\nGrAI online, with a MAE (Mean Absolute Error) of {mean_absolute_error(y_test, y_pred):.3f} and an R2 Score of {r2_score(y_test, y_pred):.3f}")

running = True
while running:
    course = input("Enter a course to test for (ACA-122, MAT-171, ENG-111): ")
    cluster = course_to_cluster(course.upper())
    predicted_grade = predict_student_grade(student_courses, cluster)
    predicted_letter = gpa_mapping[round(predicted_grade)]
    print(f"\nPredicted Grade: {predicted_letter} ({predicted_grade:.2f})")
    
    decision = input("Would you like to test another course? (y/n): ")
    if decision.lower() != "y":
        running = False
print("Have a nice day!")
connection_obj.close()