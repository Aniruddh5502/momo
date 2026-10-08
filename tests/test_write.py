"""
This code tests the different kinds of operations needs to be done with the write file tool. and then clean up things and also has some options to see the results of those tool operations.
"""

import os
from momobot.tools.write import write
from pathlib import Path
from rich.pretty import Pretty
from rich.console import Console

console = Console()
theme_char      =   "✽"
book_cloth      =   "#CC785C"
error           =   "#BF4D43"
focus           =   "#61AAF2"
white           =   "#FFFFFF"
black           =   "#000000"
cloud_light     =   "#BFBFBA"

    
def test_filetype(filePath:Path, content:str, print_result:bool=False, cleanup:bool=True):
    path = Path(filePath)
    result = write.invoke({"filePath":filePath, "content":content})
    if print_result:
        console.print(Pretty(result))
    
    reading_back = ""
    with open(path, 'r', encoding='utf-8') as file:
        reading_back = file.read()
    
    fileType = path.suffix
    
    if reading_back == content:
        # If reading back and the content matches then we count that as a success
        # and delete the file
        console.print(f"{theme_char}  [dim]Test {fileType:^10} File Type writing[/] [{focus}]succesfull.[/]")
        # and then we cleanup the file after the test has been done
        if cleanup:
            os.remove(filePath)
        
    else:
        console.print(f"{theme_char}  [dim]Test {fileType:^10} File Type writing[/] [{error}]failed[/]")
        
# The following calls were moved to a test class or commented out to prevent 
# execution on import, which was causing UnicodeEncodeErrors in the manager.
# test_filetype(filePath="test.md",content="# something \nsomething", cleanup=True)
# test_filetype(filePath="test.txt",content="# something \nsomething", cleanup=True)
# test_filetype(filePath="test.json",content="\"\"\"{\"key_1\":\"value_1\",\"key_2\":\"value_2\"}\"\"\", cleanup=True)
# test_filetype(filePath="main.cpp",content="\"\"\"# include<stdio.h\nstd::cout << \"Hello world\" << std::endl;\"\"\", cleanup=True)
