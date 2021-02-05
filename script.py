import os
import glob
import re
import html

from pathlib import Path
from bs4 import BeautifulSoup

import pdftotree
import tika
from tika import parser

import pandas as pd

def parse_pdf_file(file):
    pdf_to_html = pdftotree.parse(file, html_path=None, model_type=None, model_path=None, visualize=False)
    soup = BeautifulSoup(pdf_to_html, 'lxml')

    #Tika to get image links
    parsed = parser.from_file(file)
    content = parsed["content"]
    regex = r"(correct|wrong|should)\.png"
    urls = re.findall(regex, content)

    #Initial variables
    letters = ["A", "B", "C", "D", "E"]
    items = [[]]
    iteration = 0
    question = -1
    propositions = [[]]
    titles = []
    explanations = []

    question_block = False
    question_blocks = 0

    #Parsing the pdf file
    for line in soup.find_all("span", attrs={'class':'ocrx_line'}):
        for word in line.find("span", attrs={'class':'ocrx_word'}): #Get the first occurence
            if (word.string in letters):
                
                if len(propositions[question]) == 5:
                    if not question_block:
                        print("Not in question block")
                    else:
                        print("--QUESTION {} END--".format(question))
                        print("\n")
                        question_block = False
                
                try:
                    #Check if a new question block begins
                    c = line.parent.find_previous_sibling("div").find("span", attrs={'class':'ocrx_word'})
                    if c.string == "QUESTION":
                        #Checking for question integrity
                        if len(propositions[question]) == 5:
                            question_block = True
                            question_blocks += 1
                            items.append([])
                            propositions.append([])
                            question += 1
                            print("--QUESTION {} START--".format(question))

                        #Brand new question
                        elif len(propositions[question]) == 0 and question == -1:
                            question_block = True
                            question_blocks += 1
                            items.append([])
                            propositions.append([])
                            question += 1
                            print("--QUESTION {} START--".format(question))

                        #If there aren't all the 5 propositions and this is not the first
                        else:
                            items[question].clear()
                            propositions[question].clear()
                            titles.pop()
                            question_block = True
                            print("--uncompleted question detected--")
                            print("\n")
                            print("--QUESTION {} START--".format(question))

                    #Checking for explanation section
                    if c.string == "Commentaire:":
                        question_block = False

                except:
                    question_block = False
                    print("An exception was detected!")

                #Checked supposed length of answers
                right_letter = False
                for letter, length in zip(letters, range(5)):
                    if word.string == letter:
                        right_letter = len(propositions[question]) == length
                        # print("{} is on position {} and should be on {}".format(letter, len(propositions[question]), length))
                
                #Get question title
                if (word.string == "A") and question_block and right_letter:                
                    first = True
                    title = ""
                    for w in line.parent.find_previous_sibling("div").find_all("span", attrs={'class':'ocrx_word'}):
                        title += "" if first else " "
                        title += w.string
                        if first:
                            first = False
                    title = re.sub(r'QUESTION\sN°\s(\d)+\s', '', title) #Remove question number from the title
                    title = html.unescape(title)
                    titles.append(title)
                    print("-title detected")

                if right_letter:
                    print(word.string)
                    
                #Match the correct answers
                if question_block and right_letter:
                    text = "t" if line.parent.find_previous_sibling().name == "figure" else ""

                    #Append only correct and should answers
                    if text == "t":
                        try:
                            if urls[iteration] == "wrong":
                                text = ""
                        except:
                            text = ""
                        iteration += 1
                    items[question].append(word.string + text)

                #Get the item text
                if question_block and right_letter:
                    string = ""
                    first = True
                    for w in line.parent.find_all("span", attrs={'class':'ocrx_word'}):
                        string += "" if first else " " #Adding space between words
                        string += w.string
                        if first:
                            first = False


                    reg1 = word.string + " - " #Remove "A - "
                    reg2 = word.string + ". " #Remove "A. "
                    string = re.sub(reg1, '', string)
                    string = re.sub(reg2, '', string)
                    string = html.unescape(string)
                    propositions[question].append(string)
                    # print("The proposition was appended!")

                #Get the explanation
                if question_block and right_letter:
                    if word.string == "E":
                        explanation = ""
                        first = True

                        #Adding extra check when accessing explanations
                        try:
                            if line.parent.find_next_sibling("div").find("span", attrs={"class":"ocrx_word"}).string == "Commentaire:":
                                for w in line.parent.find_next_sibling("div").find_all("span", attrs={"class":"ocrx_word"}):
                                    explanation += "" if first else " "
                                    explanation += w.string
                                    if first:
                                        first = False
                        except:
                            explanation = ""
                        
                        explanations.append(explanation)
                        print("-explanation detected")

    #Account for errors in the last question (not detected by the loop)
    if len(propositions[-1]) != 5 and len(titles) != 0:
        question_blocks -= 1
        propositions.pop()
        items.pop()
        titles.pop()
                        
    #Get correct answers in a list that contains the letters
    correct_items = []
    for index in range(len(items)):
        correct_items.append([item[0] for item in items[index] if len(item) > 1])
        
    print("\n")
    print("Results:")
    print("\tQuestions: {}".format(question_blocks))
    print("\tTitles: {}".format(len(titles)))
    print("\tExplanations: {}".format(len(explanations)))

    question_data = {}
    for idx in range(len(titles)):
        question_data[idx] = {
            "title" : titles[idx],
            "itemA" : propositions[idx][0],
            "itemB" : propositions[idx][1],
            "itemC" : propositions[idx][2],
            "itemD" : propositions[idx][3],
            "itemE" : propositions[idx][4],
            "correctA" : True if "A" in correct_items[idx] else False,
            "correctB" : True if "B" in correct_items[idx] else False,
            "correctC" : True if "C" in correct_items[idx] else False,
            "correctD" : True if "D" in correct_items[idx] else False,
            "correctE" : True if "E" in correct_items[idx] else False,
            "explanation" : explanations[idx]
        }

    return question_data

folder = "data\\pdf"
files = glob.glob(os.path.join(folder, "*.pdf"))

column_names = [
    "lesson",
    "title",
    "itemA", "itemB", "itemC", "itemD", "itemE",
    "correctA", "correctB", "correctC", "correctD", "correctE",
    "explanation"
]
database = pd.DataFrame(columns=column_names)
for file in files:
    print("Processing file: {}".format(file))
    parsed_questions = parse_pdf_file(file)
    filename = Path(file).stem #Getting the file name without the extension
    filename = re.sub(r'\s-\s\d', "", filename)
    filename = filename.lstrip("0")

    for idx, question in parsed_questions.items():
        question["lesson"] = filename #Saving filename as lesson
        row = pd.Series(question)
        database = database.append(row, ignore_index=True)
    

#Creating the file
database.to_csv("data.csv")

