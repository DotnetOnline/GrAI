# Ethan Otero, 1/22/25
# This code is sufficient in acquiring course codes and their associated course titles through the ACC website; it's marginally successful in acquiring descriptions/competencies as well, 
# but due to inconsistent formatting on the website it scrapes from, such cases would have to individually accounted for (a skill I unfortunately do not possess for the time being).

import sqlite3
import requests
from bs4 import BeautifulSoup

from Startup import DB

startSearch = 24 # COID to start on
endSearch = 4244 # COID to end on 


connection_obj = sqlite3.connect(DB) 
cursor = connection_obj.cursor()

def yoinkHeader(webSoup): # 
    '''
    Request the first header in the associated "soup" and convert it into a string. 
    Args:
        webSoup: parsed BS4 variable
    Returns:
        header: formatted header
    '''
    header = str(webSoup.select_one('h1'))
    if not header.find("Resource Not Found") == -1 and not header.find("502 Bad Gateway") == -1:
        return("404")
    header = header.replace('<h1 id="course_preview_title">', '')
    header = header.replace("</h1>", '')
    return header

def updateCoid(desc, title, comp, url, code, startSearch,): # 
    '''
    Update rows in the SQL table that share COIDs (course IDs) to prevent duplicate entries when the program is run on an existing dataset. 
    
    
    Args:
        desc: course description
        title: course title
        comp: course competencies
        url: link to the course description page
        code: course code
        startSearch: current incrementation of the function; functions as the COID
    '''
    updateStr = "UPDATE courses SET url = ?, code = ?"
    updateList = [url, code]
    if title != "NULL":
        updateStr += ", title = ?"
        updateList.append(title)
    if desc != "NULL":
        updateStr += ", desc = ?"
        updateList.append(desc)
    if comp != "NULL":
        updateStr += ", comp = ?"
        updateList.append(comp)
    finalStr = updateStr + " WHERE coid = ?"
    updateList.append(startSearch)
    finalTuple = tuple(updateList)
    print(finalStr)
    print(finalTuple)
    cursor.execute(finalStr, finalTuple)
    connection_obj.commit()

def updateCode(desc, title, comp, url, code, startSearch,):
    '''
    Update rows in the SQL table that share course codes (e.g. ENG-112, CIS-115) to prevent duplicate entries when the program detects another listing for a course.
    

    Args:
        desc: course description
        title: course title
        comp: course competencies
        url: link to the course description page
        code: course code
        startSearch: current incrementation of the function; functions as the COID
    '''
    updateStr = "UPDATE courses SET url = ?, coid = ?"
    updateList = [url, startSearch]
    if title != "NULL":
        updateStr += ", title = ?"
        updateList.append(title)
    if desc != "NULL":
        updateStr += ", desc = ?"
        updateList.append(desc)
    if comp != "NULL":
        updateStr += ", comp = ?"
        updateList.append(comp)
    finalStr = updateStr + " WHERE code = ?"
    updateList.append(code)
    finalTuple = tuple(updateList)
    print(finalStr)
    print(finalTuple)
    cursor.execute(finalStr, finalTuple)
    connection_obj.commit()
    
url = 'https://catalog.alamancecc.edu/preview_course_nopop.php?catoid=7&coid=24'

cursor.execute("CREATE TABLE IF NOT EXISTS courses (coid INT, code STRING, title STRING, desc STRING, comp STRING, url STRING)")

while startSearch < endSearch + 1:
    url = f'https://catalog.alamancecc.edu/preview_course_nopop.php?catoid=7&coid={startSearch}'
    r = requests.get(url)
    webSoup = BeautifulSoup(r.content, 'html.parser')

    header = yoinkHeader(webSoup)
    if not header == "404":         
        code = header[:header.find("-")].strip()
        title = header[header.find("-") + 1:].strip()
        try:
            rows = webSoup.select('tbody tr')
            print(rows)
            desc = str(rows[0])
            desc = desc.replace('<tr>\n<td>', '')
            desc = desc.replace("</td>\n</tr>", '')
            try:
                comp = str(rows[2])
                comp = comp.replace('<tr>\n<td>', '')
                comp = comp.replace("</td>\n</tr>", '')
                comp = comp.replace("<br/>", '')
            except:
                comp = "NULL"
        except:
            desc = "NULL"
            comp = "NULL"
        print(code)
        print(title)
        print(desc)
        print(comp)
        print(url)
        print(startSearch)
        cursor.execute("SELECT 1 FROM courses WHERE code = ?", (code,))
        existingCode = cursor.fetchone()
        if existingCode: 
            updateCode(desc, title, comp, url, code, startSearch,)
            print("update Code")
               
        else:
            cursor.execute("SELECT 1 FROM courses WHERE coid = ?", (startSearch,))
            existingCoid = cursor.fetchone() 
            print(title)
            if existingCoid:
                updateCoid(desc, title, comp, url, code, startSearch,)
                print("update Coid")
            else:
                cursor.execute("INSERT INTO courses (coid, code, title, desc, comp, url) VALUES (?, ?, ?, ?, ?, ?)", (startSearch, code, title, desc, comp, url,))
                print("new")
        connection_obj.commit()
    else:
        print("Page Not Found")
    startSearch+=1
