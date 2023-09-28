import azure.functions as func
import logging
import qrcode
from PIL import Image, ImageDraw
import math
import random
from flask import Flask, request, jsonify,Response
import os
import io
from urllib.parse import quote
import string
from azure.storage.blob import BlobServiceClient

storage_account_key = "5jcZFJnXTIBEKJIPSd/2e6Ht/KwGKlNfk/9Ja5cmu+1cahOeFkyU7a1dUzb0kIZza4G0u5hfedCZ+ASt4psqrQ=="
connection_string = "DefaultEndpointsProtocol=https;AccountName=qrstoragefortest;AccountKey=5jcZFJnXTIBEKJIPSd/2e6Ht/KwGKlNfk/9Ja5cmu+1cahOeFkyU7a1dUzb0kIZza4G0u5hfedCZ+ASt4psqrQ==;EndpointSuffix=core.windows.net"
sas_token = 'sp=r&st=2023-09-25T21:33:36Z&se=2023-09-26T05:33:36Z&sv=2022-11-02&sr=c&sig=jQ9OulguuwNQp0aPfS8Av1LxrxdmiIEesZrEd883qKA%3D'
storage_account_name = "qrstoragefortest"
container_name = "qrcontainer"

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

def initial_qr_setup(data):
    qr = qrcode.QRCode(
        version=5,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=10,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr

def drw_initial_image(qr,background_color):
    matrix = qr.get_matrix()

    width, height = len(matrix[0]), len(matrix)

    img = Image.new('RGBA', (width * 10, height * 10), background_color)
    draw = ImageDraw.Draw(img)

    return matrix,width,height,img,draw

def drw_initial_round_image(qr,background_color):
    matrix = qr.get_matrix()

    width, height = len(matrix[0]), len(matrix)

    center_x, center_y = (((width) * 10 ) // 2) , (((height) * 10 ) // 2)

    flag = True

    for row in range(height):
        for col in range(width):
            if matrix[row][col] and flag:
                finder_pattern_row = row
                finder_pattern_col = col
                flag = False

    flag = True

    circle_start_point_x = (finder_pattern_col-3) * 10 + 9
    circle_start_point_y = (finder_pattern_row-3) * 10 + 9

    radius = int(math.sqrt((center_x-circle_start_point_x)**2 + (center_y-circle_start_point_y)**2))

    img = Image.new("RGBA", (radius * 2, radius * 2), background_color)

    mask = Image.new("L", (radius * 2, radius * 2), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, radius * 2, radius * 2), fill=255)

    img.putalpha(mask)
    draw = ImageDraw.Draw(img)

    return matrix,width,height,img,draw,circle_start_point_x,circle_start_point_y

def add_logo(image,logo):
     basewidth = 100

     wpercent = (basewidth/float(logo.size[0]))
     hsize = int((float(logo.size[1])*float(wpercent)))
     logo = logo.resize((basewidth, hsize), Image.LANCZOS)

     pos = ((image.size[0] - logo.size[0] + 10) // 2,
	    (image.size[1] - logo.size[1] + 10) // 2)
     
     return logo,pos

def drw_rectangel(gap_x,gap_y,row, col, isFinder,draw,defiendRadius,module_color):
        center_x, center_y = col * 10 + 9+gap_x, row * 10 + 9+gap_y
        radius = defiendRadius
        if isFinder:
            draw.rectangle([(center_x - radius, center_y - radius),
                        (center_x + radius, center_y + radius)],
                        fill=module_color)
            
        if not isFinder:
            draw.rectangle([(center_x - radius, center_y - radius),
                        (center_x + radius, center_y + radius)],
                        fill=module_color,outline='gray')

def get_radius_gap(width, height,matrix):
     
    flag = True

    for row in range(height):
        for col in range(width):
            if matrix[row][col] and flag:
                finder_pattern_row = row
                finder_pattern_col = col
                flag = False

    flag = True

    circle_start_point_x = (finder_pattern_col-3) * 10 + 9
    circle_start_point_y = (finder_pattern_row-3) * 10 + 9
    center_x, center_y = (((width) * 10 ) // 2) , (((height) * 10 ) // 2)
    radius = int(math.sqrt((center_x-circle_start_point_x)**2 + (center_y-circle_start_point_y)**2))
    
    gap_x = radius - center_x
    gap_y = radius - center_y
    return gap_x,gap_y,radius 

def drw_general_rectangel(gap_x,gap_y,row, col,draw,defiendRadius,module_color):
        center_x, center_y = col * 10 + 9+gap_x, row * 10 + 9+gap_y
        radius = defiendRadius

        draw.rectangle([(center_x - radius, center_y - radius),
                        (center_x + radius, center_y + radius)],
                        fill=module_color)

def drw_horizontal_line(gap_x,gap_y,top_left_x,top_left_y,right_bottom_x,right_bottom_y,draw,module_color):
            tx = (top_left_x*10)+9
            ty = (top_left_y*10)+7
            bx = (right_bottom_x*10)+9
            by = (right_bottom_y*10)+11

            draw.rectangle([(tx+gap_x, ty+gap_y),
                        (bx+gap_x, by+gap_y)],
                        fill=module_color)
            
def drw_vertical_line(gap_x,gap_y,top_left_x,top_left_y,right_bottom_x,right_bottom_y,draw,module_color):
            tx = (top_left_x*10)+7
            ty = (top_left_y*10)+9
            bx = (right_bottom_x*10)+11
            by = (right_bottom_y*10)+9

            draw.rectangle([(tx+gap_x, ty+gap_y),
                        (bx+gap_x, by+gap_y)],
                        fill=module_color)

def drw_small_circle(gap_x,gap_y,row,col,draw,module_color):
        center_x, center_y = col * 10 + 9+gap_x, row * 10 + 9+gap_y
        radius = 2
        draw.ellipse((center_x - radius, center_y - radius, center_x + radius, center_y + radius), fill=module_color)

def drw_circle(gap_x,gap_y,row,col,draw,module_color):
        center_x, center_y = col * 10 + 9+gap_x, row * 10 + 9+gap_y
        radius = 4
        draw.ellipse((center_x - radius, center_y - radius, center_x + radius, center_y + radius), fill=module_color)

def drw_polygon(gap_x,gap_y,row,col,draw,module_color):
        center_x, center_y = col * 10 + 9+gap_x, row * 10 + 9+gap_y
        radius = 5
        draw.polygon([(center_x, center_y - radius),
                          (center_x + radius, center_y),
                          (center_x, center_y + radius),
                          (center_x - radius, center_y)],
                          fill=module_color)

def drw_triangle(gap_x,gap_y,row, col,draw,defiendRadius,module_color):
        center_x, center_y = col * 10 + 9+gap_x, row * 10 + 9+gap_y
        radius = defiendRadius
        triangle_height = radius * math.sqrt(3)
        triangle_points = [
            (center_x, center_y - radius),
            (center_x + radius * math.cos(math.radians(30)), center_y + triangle_height / 2),
            (center_x - radius * math.cos(math.radians(30)), center_y + triangle_height / 2)
        ]
        draw.polygon(triangle_points,fill=module_color)

def drw_line_modules(gap_x,gap_y,height,width,finder_pattern_col,finder_pattern_row,matrix,draw,module_color):
    drawing_possitions_horizontal = []
    drawing_possitions_vertical = []
    horizontal = []
    vertical = []
    setAllHorizontal = []
    setAllVertical = []
    drewn_points = []
    all_points = []
    isExistHorizontal = False
    isHorizontalDraw = False
    isExistVertical = False
    isVerticalDraw = False

    for row in range(height):
        for col in range(width):
                
                if col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= finder_pattern_row + 6 and row >= finder_pattern_row or col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= height - finder_pattern_row - 1  and row >= height - finder_pattern_row - 7 or row <= finder_pattern_row + 6 and row >= finder_pattern_row and col <= width - finder_pattern_col - 1 and col >= width - finder_pattern_col - 7:
                    continue
                
                if matrix[row][col]:

                    all_points.append((row,col))

                count = 0
                isJump = True
                if matrix[row][col]:
                    for x in range(col ,width - finder_pattern_col ,1):
                        if matrix[row][x] and isJump and not (col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= finder_pattern_row + 6 and row >= finder_pattern_row or col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= height - finder_pattern_row - 1  and row >= height - finder_pattern_row - 7 or row <= finder_pattern_row + 6 and row >= finder_pattern_row and col <= width - finder_pattern_col - 1 and col >= width - finder_pattern_col - 7):
                            count = count + 1
                        else:
                             isJump = False

                isJump = True
               
                if count > 1 :
                     for x in range(col ,width - finder_pattern_col ,1):
                        if matrix[row][x] and isJump and not (col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= finder_pattern_row + 6 and row >= finder_pattern_row or col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= height - finder_pattern_row - 1  and row >= height - finder_pattern_row - 7 or row <= finder_pattern_row + 6 and row >= finder_pattern_row and col <= width - finder_pattern_col - 1 and col >= width - finder_pattern_col - 7):

                            if (row, x) not in setAllHorizontal or len(setAllHorizontal) == 0:
                                horizontal.append((row, x))
                            setAllHorizontal.append((row, x))

                        else:
                             isJump = False


                count = 0
                isJump = True
                if matrix[row][col]:
                    for y in range(row ,height - finder_pattern_row ,1):
                        if matrix[y][col] and isJump and not (col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= finder_pattern_row + 6 and row >= finder_pattern_row or col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= height - finder_pattern_row - 1  and row >= height - finder_pattern_row - 7 or row <= finder_pattern_row + 6 and row >= finder_pattern_row and col <= width - finder_pattern_col - 1 and col >= width - finder_pattern_col - 7):
                            count = count + 1
                        else:
                             isJump = False

                isJump = True
               
                if count > 1:
                     for y in range(row ,height - finder_pattern_row ,1):
                        if matrix[y][col] and isJump and not (col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= finder_pattern_row + 6 and row >= finder_pattern_row or col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= height - finder_pattern_row - 1  and row >= height - finder_pattern_row - 7 or row <= finder_pattern_row + 6 and row >= finder_pattern_row and col <= width - finder_pattern_col - 1 and col >= width - finder_pattern_col - 7):
                            if (y, col) not in setAllVertical or len(setAllVertical) == 0:
                                vertical.append((y, col))
                            setAllVertical.append((y, col))

                        else:
                             isJump = False

                if not len(horizontal) == 0:
                    drawing_possitions_horizontal.append(horizontal)
                    horizontal = []

                if not len(vertical) == 0:
                    drawing_possitions_vertical.append(vertical)
                    vertical = []


    for row in range(height):
        for col in range(width):
             
            for i in range(len(drawing_possitions_horizontal)):
                    if len(drewn_points) == 0:
                       for j in range(len(drawing_possitions_horizontal[i])):
                                drewn_points.append(drawing_possitions_horizontal[i][j])
                       drw_horizontal_line(gap_x,gap_y,drawing_possitions_horizontal[i][0][1],drawing_possitions_horizontal[i][0][0],drawing_possitions_horizontal[i][len(drawing_possitions_horizontal[i])-1][1],drawing_possitions_horizontal[i][len(drawing_possitions_horizontal[i])-1][0],draw,module_color)
                       drw_small_circle(gap_x,gap_y,drawing_possitions_horizontal[i][0][0],drawing_possitions_horizontal[i][0][1],draw,module_color)
                       drw_small_circle(gap_x,gap_y,drawing_possitions_horizontal[i][len(drawing_possitions_horizontal[i])-1][0],drawing_possitions_horizontal[i][len(drawing_possitions_horizontal[i])-1][1],draw,module_color)
                       isHorizontalDraw = True
                    else:
                        for j in range(len(drawing_possitions_horizontal[i])):
                            if drawing_possitions_horizontal[i][j] in drewn_points:
                                isExistHorizontal = True
                                     
                    if not isExistHorizontal and not isHorizontalDraw:
                        for k in range(len(drawing_possitions_horizontal[i])):
                            drewn_points.append(drawing_possitions_horizontal[i][k]) 
                            isHorizontalDraw = True 
                        drw_horizontal_line(gap_x,gap_y,drawing_possitions_horizontal[i][0][1],drawing_possitions_horizontal[i][0][0],drawing_possitions_horizontal[i][len(drawing_possitions_horizontal[i])-1][1],drawing_possitions_horizontal[i][len(drawing_possitions_horizontal[i])-1][0],draw,module_color)
                        drw_small_circle(gap_x,gap_y,drawing_possitions_horizontal[i][0][0],drawing_possitions_horizontal[i][0][1],draw,module_color)
                        drw_small_circle(gap_x,gap_y,drawing_possitions_horizontal[i][len(drawing_possitions_horizontal[i])-1][0],drawing_possitions_horizontal[i][len(drawing_possitions_horizontal[i])-1][1],draw,module_color)

                    isExistHorizontal = False


            for a in range(len(drawing_possitions_vertical)):
                    if len(drewn_points) == 0:
                       for b in range(len(drawing_possitions_vertical[a])):
                                drewn_points.append(drawing_possitions_vertical[a][b])
                       drw_vertical_line(gap_x,gap_y,drawing_possitions_vertical[a][0][1],drawing_possitions_vertical[a][0][0],drawing_possitions_vertical[a][len(drawing_possitions_vertical[a])-1][1],drawing_possitions_vertical[a][len(drawing_possitions_vertical[a])-1][0],draw,module_color)
                       drw_small_circle(gap_x,gap_y,drawing_possitions_vertical[a][0][0],drawing_possitions_vertical[a][0][1],draw,module_color)
                       drw_small_circle(gap_x,gap_y,drawing_possitions_vertical[a][len(drawing_possitions_vertical[a])-1][0],drawing_possitions_vertical[a][len(drawing_possitions_vertical[a])-1][1],draw,module_color)
                       isVerticalDraw = True
                    else:
                        for b in range(len(drawing_possitions_vertical[a])):
                            if drawing_possitions_vertical[a][b] in drewn_points:
                                isExistVertical = True
                                     
                    if not isExistVertical and not isVerticalDraw:
                        for c in range(len(drawing_possitions_vertical[a])):
                            drewn_points.append(drawing_possitions_vertical[a][c]) 
                            isVerticalDraw = True
                        drw_vertical_line(gap_x,gap_y,drawing_possitions_vertical[a][0][1],drawing_possitions_vertical[a][0][0],drawing_possitions_vertical[a][len(drawing_possitions_vertical[a])-1][1],drawing_possitions_vertical[a][len(drawing_possitions_vertical[a])-1][0],draw,module_color)
                        drw_small_circle(gap_x,gap_y,drawing_possitions_vertical[a][0][0],drawing_possitions_vertical[a][0][1],draw,module_color)
                        drw_small_circle(gap_x,gap_y,drawing_possitions_vertical[a][len(drawing_possitions_vertical[a])-1][0],drawing_possitions_vertical[a][len(drawing_possitions_vertical[a])-1][1],draw,module_color) 

                    isExistVertical = False

            isExistHorizontal = False
            isHorizontalDraw = False
            isExistVertical = False
            isVerticalDraw = False


    for a in range(len(all_points)):
         if all_points[a] not in drewn_points:
            drw_small_circle(gap_x,gap_y,all_points[a][0],all_points[a][1],draw,module_color)

def drw_various_finder_patterns(x_cordination,y_cordination,border_color,draw,rec_no):  

     if rec_no == 1:
        corner_radius = 13
        border_rectangle = [
            (x_cordination + 4, y_cordination + 4),
            (x_cordination+74, y_cordination+74)
        ]

     if rec_no == 2:
        corner_radius = 7
        border_rectangle = [
            (x_cordination + 5, y_cordination + 5),
            (x_cordination+53, y_cordination+53)
        ]

     if rec_no == 3:
        corner_radius = 7
        border_rectangle = [
            (x_cordination + 4, y_cordination + 4),
            (x_cordination+34, y_cordination+34)
        ]


     draw.rounded_rectangle(
         border_rectangle,
         corner_radius,
         fill=border_color
     )

def drw_finder_patern_01(gap_x,gap_y,row,col,width,height,draw,module_color,background_color):
        # top right finder pattern
        for y in range(width - col - 7,width - col,1):
            drw_rectangel(gap_x,gap_y,row ,y ,True,draw,5,module_color )
            drw_rectangel(gap_x,gap_y,row + 6 ,y ,True,draw,5,module_color )

            if y == width - col - 3 or y == width - col - 4 or y == width - col - 5:
                drw_rectangel(gap_x,gap_y,row + 2 ,y ,True,draw,5,module_color)
                drw_rectangel(gap_x,gap_y,row + 3 ,y ,True,draw,5,module_color)
                drw_rectangel(gap_x,gap_y,row + 4 ,y ,True,draw,5,module_color)

        for x in range(row ,row + 7 ,1):
            drw_rectangel(gap_x,gap_y,x ,width - col - 1 ,True,draw,5,module_color )
            drw_rectangel(gap_x,gap_y,x ,width - col - 7 ,True,draw,5,module_color )

        # top left finder pattern
        for y in range(col,col + 7,1):
            drw_rectangel(gap_x,gap_y,row ,y ,True,draw,5,module_color )
            drw_rectangel(gap_x,gap_y,row + 6,y ,True,draw,5,module_color )

            if y ==  col + 2 or y ==  col + 3 or y ==  col + 4:
                drw_rectangel(gap_x,gap_y,row + 2 ,y ,True,draw,5,module_color)
                drw_rectangel(gap_x,gap_y,row + 3 ,y ,True,draw,5,module_color)
                drw_rectangel(gap_x,gap_y,row + 4 ,y ,True,draw,5,module_color)

        for x in range(row ,row + 7 ,1):
            drw_rectangel(gap_x,gap_y,x ,col ,True,draw,5,module_color )
            drw_rectangel(gap_x,gap_y,x ,col + 6 ,True ,draw,5,module_color)

        # bottom left finder pattern
        for x in range(height - row - 7 ,height - row,1):
            drw_rectangel(gap_x,gap_y,x ,col ,True,draw,5,module_color )
            drw_rectangel(gap_x,gap_y,x ,col + 6 ,True,draw,5,module_color )

        for y in range(col,col + 7,1):
            drw_rectangel(gap_x,gap_y,height - row - 1 ,y ,True,draw,5,module_color )
            drw_rectangel(gap_x,gap_y,height - row - 7 ,y ,True,draw,5,module_color )

            if y ==  col + 2 or y ==  col + 3 or y ==  col + 4:
                drw_rectangel(gap_x,gap_y,height - row - 3 ,y ,True,draw,5,module_color)
                drw_rectangel(gap_x,gap_y,height - row - 4 ,y ,True,draw,5,module_color)
                drw_rectangel(gap_x,gap_y,height - row - 5 ,y ,True,draw,5,module_color)

def drw_finder_patern_02(gap_x,gap_y,row,col,width,height,draw,module_color,background_color):
    drw_various_finder_patterns((col * 10)+gap_x,(row * 10)+gap_y,module_color,draw,1)
    drw_various_finder_patterns(((col + 1) * 10)+gap_x,((row + 1) * 10)+gap_y,background_color,draw,2)
    drw_various_finder_patterns(((col + 2) * 10)+gap_x,((row + 2) * 10)+gap_y,module_color,draw,3)

    drw_various_finder_patterns(((width - col - 7) * 10)+gap_x,(row * 10)+gap_y,module_color,draw,1)
    drw_various_finder_patterns(((width - col - 6) * 10)+gap_x,((row + 1) * 10)+gap_y,background_color,draw,2)
    drw_various_finder_patterns(((width - col - 5) * 10)+gap_x,((row + 2) * 10)+gap_y,module_color,draw,3)

    drw_various_finder_patterns((col * 10)+gap_x,((height - row - 7) * 10)+gap_y,module_color,draw,1)
    drw_various_finder_patterns(((col + 1) * 10)+gap_x,((height - row - 6) * 10)+gap_y,background_color,draw,2)
    drw_various_finder_patterns(((col + 2) * 10)+gap_x,((height - row - 5) * 10)+gap_y,module_color,draw,3)
     
def drw_finder_patern_03(gap_x,gap_y,row,col,width,height,draw,module_color,background_color):
    drw_various_finder_patterns((col * 10)+gap_x,(row * 10)+gap_y,module_color,draw,1)
    drw_various_finder_patterns(((col + 1) * 10)+gap_x,((row + 1) * 10)+gap_y,background_color,draw,2)
    drw_various_finder_patterns(((col + 2) * 10)+gap_x,((row + 2) * 10)+gap_y,module_color,draw,3)

    drw_various_finder_patterns(((width - col - 7) * 10)+gap_x,(row * 10)+gap_y,module_color,draw,1)
    drw_various_finder_patterns(((width - col - 6) * 10)+gap_x,((row + 1) * 10)+gap_y,background_color,draw,2)
    drw_various_finder_patterns(((width - col - 5) * 10)+gap_x,((row + 2) * 10)+gap_y,module_color,draw,3)

    drw_various_finder_patterns((col * 10)+gap_x,((height - row - 7) * 10)+gap_y,module_color,draw,1)
    drw_various_finder_patterns(((col + 1) * 10)+gap_x,((height - row - 6) * 10)+gap_y,background_color,draw,2)
    drw_various_finder_patterns(((col + 2) * 10)+gap_x,((height - row - 5) * 10)+gap_y,module_color,draw,3)

    drw_rectangel(gap_x,gap_y,row ,col ,True,draw,5,module_color )
    drw_rectangel(gap_x,gap_y,row + 2 ,col + 2 ,True,draw,5,module_color )

    drw_rectangel(gap_x,gap_y,row ,width - col - 1,True,draw,5,module_color )
    drw_rectangel(gap_x,gap_y,row + 2 ,width - col - 3 ,True,draw,5,module_color )

    drw_rectangel(gap_x,gap_y,height - row - 1 ,col,True,draw,5,module_color )
    drw_rectangel(gap_x,gap_y,height - row - 3 ,col + 2 ,True,draw,5,module_color )

def drw_finder_patern_04(gap_x,gap_y,row,col,width,height,draw,module_color,background_color):

    drw_various_finder_patterns((col * 10)+gap_x,(row * 10)+gap_y,module_color,draw,1)
    drw_various_finder_patterns(((col + 1) * 10)+gap_x,((row + 1) * 10)+gap_y,background_color,draw,2)
    drw_various_finder_patterns(((col + 2) * 10)+gap_x,((row + 2) * 10)+gap_y,module_color,draw,3)

    drw_various_finder_patterns(((width - col - 7) * 10)+gap_x,(row * 10)+gap_y,module_color,draw,1)
    drw_various_finder_patterns(((width - col - 6) * 10)+gap_x,((row + 1) * 10)+gap_y,background_color,draw,2)
    drw_various_finder_patterns(((width - col - 5) * 10)+gap_x,((row + 2) * 10)+gap_y,module_color,draw,3)

    drw_various_finder_patterns((col * 10)+gap_x,((height - row - 7) * 10)+gap_y,module_color,draw,1)
    drw_various_finder_patterns(((col + 1) * 10)+gap_x,((height - row - 6) * 10)+gap_y,background_color,draw,2)
    drw_various_finder_patterns(((col + 2) * 10)+gap_x,((height - row - 5) * 10)+gap_y,module_color,draw,3)

    drw_rectangel(gap_x,gap_y,row ,col ,True,draw,5,module_color)
    drw_rectangel(gap_x,gap_y,row + 2 ,col + 2 ,True,draw,5,module_color)

    drw_rectangel(gap_x,gap_y,row ,width - col - 1,True,draw,5,module_color )
    drw_rectangel(gap_x,gap_y,row + 2 ,width - col - 3 ,True,draw,5,module_color)

    drw_rectangel(gap_x,gap_y,height - row - 1 ,col,True,draw,5,module_color )
    drw_rectangel(gap_x,gap_y,height - row - 3 ,col + 2 ,True,draw,5,module_color )

    drw_rectangel(gap_x,gap_y,row + 6 ,col + 6 ,True,draw,5,module_color )
    drw_rectangel(gap_x,gap_y,row + 4 ,col + 4 ,True,draw,5,module_color )

    drw_rectangel(gap_x,gap_y,row + 6 ,width - col - 7,True,draw,5,module_color )
    drw_rectangel(gap_x,gap_y,row + 4 ,width - col - 5,True,draw,5,module_color )

    drw_rectangel(gap_x,gap_y,height - row - 7 ,col + 6,True,draw,5,module_color )
    drw_rectangel(gap_x,gap_y,height - row - 5 ,col + 4 ,True,draw,5,module_color )

def drw_border(border_width,border_color,width, height,draw):
        corner_radius = 10 
        border_rectangle = [
            (border_width-5, border_width-5),
            (width * 10 - border_width+12, height * 10 - border_width+12)
        ]
        draw.rounded_rectangle(
            border_rectangle,
            corner_radius,
            fill=border_color
        )

def drw_background_rounded_rectangle(border_color,width, height,draw,finder_pattern_row, finder_pattern_col,gap_xt,gap_yt):
        corner_radius = 10 
        border_rectangle = [
            (finder_pattern_row*10+gap_xt-5, finder_pattern_col*10+gap_yt-5),
            (((width-finder_pattern_col) * 10 )+gap_xt+13, ((height-finder_pattern_row) * 10)+gap_yt+13)
        ]
        draw.rounded_rectangle(
            border_rectangle,
            corner_radius,
            fill=border_color
        )

def drw_background_circles(gap_x,gap_y,width, height ,matrix_row, matrix_col,draw,avoid_rect,module_color):
        center_x, center_y = (((width * 10)) // 2)+5 , (((height * 10)) // 2)+5

        point_x = (matrix_col ) * 10 + 9
        point_y = matrix_row * 10 + 9

        point_x1 = (width- matrix_col-1)*10
        point_y1 = (height-matrix_row-1)*10
        point_x2 = (matrix_col)*10
        point_y2 = (matrix_row)*10
        radius = int(math.sqrt((point_x - center_x)**2 + (point_y - center_y)**2)) - 10
        dot_size = 2
        dot_spacing = 20
        
        for y in range(center_y - radius, center_y + radius, dot_spacing):
            for x in range(center_x - radius, center_x + radius, dot_spacing):
                distance = math.sqrt((x - center_x)**2 + (y - center_y)**2)
                if distance <= radius - 15 and x < point_x1 and y < point_y1:
                    if avoid_rect[0][0] <= x <= avoid_rect[1][0] and avoid_rect[0][1] <= y <= avoid_rect[1][1]:
                        continue

                    draw.ellipse((x - dot_size+gap_x, y - dot_size+gap_y, x + dot_size+gap_x, y + dot_size+gap_y), fill=module_color)

        for y in range(center_y + radius, center_y - radius, -1*dot_spacing):
            for x in range(center_x + radius, center_x - radius, -1*dot_spacing):
                distance = math.sqrt((x - center_x)**2 + (y - center_y)**2)
                if distance <= radius - 15 and x > point_x2 and y > point_y2:
                    if avoid_rect[0][0] <= x <= avoid_rect[1][0] and avoid_rect[0][1] <= y <= avoid_rect[1][1]:
                        continue

                    draw.ellipse((x - dot_size+gap_x, y - dot_size+gap_y, x + dot_size+gap_x, y + dot_size+gap_y), fill=module_color)

def drw_background_circles_for_large_circle(gap_x,gap_y,width, height ,matrix_row, matrix_col,draw,avoid_rect,module_color):
        center_x, center_y = ((width * 10) // 2)+5, ((height * 10) // 2)+5

        point_x = (matrix_col ) * 10 + 9
        point_y = matrix_row * 10 + 9

        point_x1 = (width- matrix_col-1)*10
        point_y1 = (height-matrix_row-1)*10
        point_x2 = (matrix_col)*10
        point_y2 = (matrix_row)*10

        radius = int(math.sqrt((point_x - center_x)**2 + (point_y - center_y)**2))
        dot_size = 2
        dot_spacing = 20
        
        for y in range(center_y - radius, center_y + radius, dot_spacing):
            for x in range(center_x - radius, center_x + radius, dot_spacing):
                distance = math.sqrt((x - center_x)**2 + (y - center_y)**2)
                if distance <= radius + 10 and x < point_x1 and y < point_y1:
                    if avoid_rect[0][0] <= y <= avoid_rect[1][0] and avoid_rect[0][1] <= x <= avoid_rect[1][1]:
                        continue

                    draw.ellipse((x - dot_size+gap_x, y - dot_size+gap_y, x + dot_size+gap_x, y + dot_size+gap_y), fill=module_color)

        for y in range(center_y + radius, center_y - radius, -1*dot_spacing):
                    for x in range(center_x + radius, center_x - radius, -1*dot_spacing):
                        distance = math.sqrt((x - center_x)**2 + (y - center_y)**2)
                        if distance <= radius + 10 and x > point_x2 and y > point_y2:
                            if avoid_rect[0][0] <= y <= avoid_rect[1][0] and avoid_rect[0][1] <= x <= avoid_rect[1][1]:
                                continue

                            draw.ellipse((x - dot_size+gap_x, y - dot_size+gap_y, x + dot_size+gap_x, y + dot_size+gap_y), fill=module_color)

def drw_background_polygon(gap_x,gap_y,width, height ,matrix_row, matrix_col,draw,avoid_rect,module_color):
        center_x, center_y = ((width * 10) // 2)+5 , ((height * 10) // 2) +5

        point_x = (matrix_col ) * 10 + 9
        point_y = matrix_row * 10 + 9

        point_x1 = (width- matrix_col-1)*10
        point_y1 = (height-matrix_row-1)*10
        point_x2 = (matrix_col)*10
        point_y2 = (matrix_row)*10
        radius = int(math.sqrt((point_x - center_x)**2 + (point_y - center_y)**2)) - 10
        polygon_size = 5
        polygon_spacing = 20
        
        for y in range(center_y - radius, center_y + radius, polygon_spacing):
            for x in range(center_x - radius, center_x + radius, polygon_spacing):
                distance = math.sqrt((x - center_x)**2 + (y - center_y)**2)
                if distance <= radius - 15 and x < point_x1 and y < point_y1:
                    if avoid_rect[0][0] <= x <= avoid_rect[1][0] and avoid_rect[0][1] <= y <= avoid_rect[1][1]:
                        continue

                    draw.polygon([(x+gap_x , y - polygon_size+gap_y), (x + polygon_size+gap_x , y+gap_y ), (x+gap_x  , y+ polygon_size+gap_y ), (x - polygon_size+gap_x , y+gap_y )], fill=module_color)


        for y in range(center_y + radius, center_y - radius, -1*polygon_spacing):
            for x in range(center_x + radius, center_x - radius, -1*polygon_spacing):
                distance = math.sqrt((x - center_x)**2 + (y - center_y)**2)
                if distance <= radius - 15 and x > point_x2 and y > point_y2:
                    if avoid_rect[0][0] <= x <= avoid_rect[1][0] and avoid_rect[0][1] <= y <= avoid_rect[1][1]:
                        continue

                    draw.polygon([(x+gap_x , y - polygon_size+gap_y), (x + polygon_size+gap_x , y+gap_y ), (x+gap_x  , y+ polygon_size+gap_y ), (x - polygon_size+gap_x , y+gap_y )], fill=module_color)

def drw_background_varius_polygon(gap_x,gap_y,width, height ,matrix_row, matrix_col,draw,avoid_rect,module_color):
        center_x, center_y = ((width * 10) // 2), ((height * 10) // 2)

        point_x = (matrix_col ) * 10 + 9
        point_y = matrix_row * 10 + 9

        point_x1 = (width- matrix_col-1)*10
        point_y1 = (height-matrix_row-1)*10
        point_x2 = (matrix_col)*10
        point_y2 = (matrix_row)*10
        radius = int(math.sqrt((point_x - center_x)**2 + (point_y - center_y)**2)) - 10
        large_polygon_size = 5
        small_polygon_size = 3
        polygon_spacing = 20
        different_polygon = True
        different_polygon2 = True
        
        for y in range(center_y - radius, center_y + radius, polygon_spacing):
            for x in range(center_x - radius, center_x + radius, polygon_spacing):
                distance = int(math.sqrt((x - center_x)**2 + (y - center_y)**2))
                if distance <= radius + 10 and x < point_x1 and y < point_y1:
                    if avoid_rect[0][0] <= y <= avoid_rect[1][0] and avoid_rect[0][1] <= x <= avoid_rect[1][1]:
                        continue

                    if different_polygon:
                        draw.polygon([(x+gap_x , y - large_polygon_size+gap_y), (x + large_polygon_size+gap_x , y+gap_y ), (x+gap_x  , y+ large_polygon_size+gap_y ), (x - large_polygon_size+gap_x , y+gap_y )], fill=module_color)

                    if not different_polygon:
                        draw.polygon([(x+gap_x , y - small_polygon_size+gap_y), (x + small_polygon_size+gap_x , y+gap_y ), (x+gap_x  , y+ small_polygon_size+gap_y ), (x - small_polygon_size+gap_x , y+gap_y )], fill=module_color)

                different_polygon = not different_polygon

        for y in range(center_y + radius, center_y - radius, -1*polygon_spacing):
            for x in range(center_x + radius, center_x - radius, -1*polygon_spacing):
                distance = int(math.sqrt((x - center_x)**2 + (y - center_y)**2))
                if distance <= radius + 10 and x > point_x2 and y > point_y2:
                    if avoid_rect[0][0] <= y <= avoid_rect[1][0] and avoid_rect[0][1] <= x <= avoid_rect[1][1]:
                        continue

                    if different_polygon2:
                        draw.polygon([(x+gap_x , y - large_polygon_size+gap_y), (x + large_polygon_size+gap_x , y+gap_y ), (x+gap_x  , y+ large_polygon_size+gap_y ), (x - large_polygon_size+gap_x , y+gap_y )], fill=module_color)

                    if not different_polygon2:
                        draw.polygon([(x+gap_x , y - small_polygon_size+gap_y), (x + small_polygon_size+gap_x , y+gap_y ), (x+gap_x  , y+ small_polygon_size+gap_y ), (x - small_polygon_size+gap_x , y+gap_y )], fill=module_color)

                different_polygon2 = not different_polygon2
            different_polygon2 = not different_polygon2                

def drw_large_rectangel(row, col,width,draw):
        center_x, center_y = col * 10 + 9, row * 10 + 9
        radius = (width - col - col)*5 
        draw.rectangle([(center_x -5 , center_y-5 ),
                        (center_x + 2*radius - 5, center_y + 2*radius - 5)],
                       fill='white')

def drw_partial_circle_around_qr(circle_start_point_x,circle_start_point_y,temp_no,draw, width, height, start_angle, end_angle,matrix_row, matrix_col,module_color):
        center_x, center_y = (((width * 10)) // 2) , (((height * 10)) // 2) 

        point_x = (matrix_col )* 10 
        point_y = (matrix_row)* 10 

        radius = int(math.sqrt((center_x-circle_start_point_x)**2 + (center_y-circle_start_point_y)**2))

        if(temp_no == 5) :

            draw.arc((point_x-60, point_y-60, (radius * 2)-point_x+60, (radius * 2)-point_y+60),
             start=start_angle, end=end_angle, width=7, fill=module_color)
            
        else:
            draw.arc((point_x-60, point_y-60, (radius * 2)-point_x+60, (radius * 2)-point_y+60),
             start=start_angle, end=end_angle, width=7, fill=module_color) 

def drw_white_rectangel(row, col,draw):
        center_x, center_y = col * 10 + 9, row * 10 + 9
        radius = 5
        draw.rectangle([(center_x - radius, center_y - radius),
                        (center_x + radius, center_y + radius)],
                       fill='white')
        
def drw_white_boundry_around_qr(row, col,width,height,draw):

        for x in range(col, width - col, 1):
            drw_white_rectangel(row - 1 , x ,draw )

        for x in range(col, width - col, 1):
            drw_white_rectangel(height - row , x ,draw )

        for y in range(row - 1, height - row + 1, 1):
            drw_white_rectangel(y , col - 1 ,draw )

        for y in range(row - 1, height - row + 1, 1):
            drw_white_rectangel(y , width - col ,draw )

def drw_circle_around_qr(radius,draw, module_color,background_color):

        draw.ellipse((0, 0,
                  radius * 2, radius * 2),
                 outline=module_color, fill=background_color, width=7)

def drw_background_rectangels(gap_x,gap_y,width, height ,matrix_row, matrix_col,draw,avoid_rect,module_color,background_color):
        center_x, center_y = ((width * 10) // 2) , ((height * 10) // 2) 

        point_x = (matrix_col ) * 10 + 9
        point_y = matrix_row * 10 + 9
        point_x1 = (width- matrix_col-1)*10
        point_y1 = (height-matrix_row-1)*10
        point_x2 = (matrix_col)*10
        point_y2 = (matrix_row)*10

        radius = int(math.sqrt((point_x - center_x)**2 + (point_y - center_y)**2)) + 10
        rectangle_size = 5
        rectangle_spacing = 10
        background_data = []
        previos_y = 0
        previos_x = 0

        for y in range(center_y - radius, center_y + radius, rectangle_spacing):
            row_data = []
            for x in range(center_x - radius, center_x + radius, rectangle_spacing):
                random_boolean = random.choice([True, False])
                distance = math.sqrt((x - center_x)**2 + (y - center_y)**2)
                if distance <= radius:
                    if avoid_rect[0][0] <= x <= avoid_rect[1][0] and avoid_rect[0][1] <= y <= avoid_rect[1][1]:
                        row_data.append(None)
                        continue

                    if not random_boolean:
                        draw.rectangle((x - rectangle_size+gap_x, y - rectangle_size+gap_y, x + rectangle_size+gap_x, y + rectangle_size+gap_y), fill=background_color)

                row_data.append(random_boolean)

            background_data.append(row_data)

        

        for y in range(center_y - radius, center_y + radius, rectangle_spacing):
            for x in range(center_x - radius, center_x + radius, rectangle_spacing):
                distance = math.sqrt((x - center_x)**2 + (y - center_y)**2)
                if distance <= radius and x < point_x1 and y < point_y1:
                    if previos_y < len(background_data) and previos_x < len(background_data[1]):
                        if background_data[previos_y][previos_x]:
                            draw.rectangle((x - rectangle_size+gap_x, y - rectangle_size+gap_y, x + rectangle_size+gap_x, y + rectangle_size+gap_y), fill=module_color,outline='gray')

                previos_x = previos_x + 1


            previos_y = previos_y + 1
            previos_x = 0

        previos_y = len(background_data)-1
        previos_x = len(background_data[1])-1

        for y in range(center_y + radius, center_y - radius, -1*rectangle_spacing):
            for x in range(center_x + radius, center_x - radius, -1*rectangle_spacing):
                distance = math.sqrt((x - center_x)**2 + (y - center_y)**2)
                if distance <= radius and x > point_x2 and y > point_y2:
                    if previos_y < len(background_data) and previos_x < len(background_data[1]):
                        if background_data[previos_y][previos_x]:
                            draw.rectangle((x - rectangle_size+gap_x, y - rectangle_size+gap_y, x + rectangle_size+gap_x, y + rectangle_size+gap_y), fill=module_color,outline='gray')

                previos_x = previos_x -1 


            previos_y = previos_y - 1
            previos_x = len(background_data[1])-1

def draw_large_rectangle_around_image(row, col, width, height, draw,background_color):

        center_x, center_y = (row // 2) - 1, (col//2) - 1
        radius_x = width + 9
        radius_y = height + 9

        draw.rectangle([(center_x + 4 - radius_x//2, center_y + 4  - radius_y//2),
                        (center_x + 7  + radius_x//2, center_y + 7  + radius_y//2)],
                       fill=background_color)

def template_01(data,finder_patern_number,module_patern,module_color,background_color):

    qr = initial_qr_setup(data)
    matrix,width,height,img,draw = drw_initial_image(qr,background_color)
    flag = True
    gap_x = 0
    gap_y = 0

    for row in range(height):
        for col in range(width):
            if matrix[row][col] and flag:
                finder_pattern_row = row
                finder_pattern_col = col
                flag = False

    flag = True

    if module_patern == '6':
         drw_line_modules(gap_x,gap_y,height,width,finder_pattern_col,finder_pattern_row,matrix,draw,module_color)
         
    else:

        for row in range(height):
            for col in range(width):
                    if matrix[row][col]:

                        if col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= finder_pattern_row + 6 and row >= finder_pattern_row or col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= height - finder_pattern_row - 1  and row >= height - finder_pattern_row - 7 or row <= finder_pattern_row + 6 and row >= finder_pattern_row and col <= width - finder_pattern_col - 1 and col >= width - finder_pattern_col - 7:
                            continue

                        if module_patern == '1':
                            drw_rectangel(gap_x,gap_y,row,col,False,draw,5,module_color)

                        if module_patern == '2':
                            drw_general_rectangel(gap_x,gap_y,row,col,draw,5,module_color)

                        if module_patern == '3':
                            drw_polygon(gap_x,gap_y,row,col,draw,module_color)

                        if module_patern == '4':
                            drw_circle(gap_x,gap_y,row,col,draw,module_color)

                        if module_patern == '5':
                            drw_triangle(gap_x,gap_y,row, col,draw,5,module_color)


    for row in range(height):
        for col in range(width):
            if matrix[row][col] and flag:
                    if finder_patern_number == '1':
                        drw_finder_patern_01(gap_x,gap_y,row,col,len(matrix[0]), len(matrix),draw,module_color)
                    elif finder_patern_number == '2':
                        drw_finder_patern_02(gap_x,gap_y,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '3':
                       drw_finder_patern_03(gap_x,gap_y,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '4':
                        drw_finder_patern_04(gap_x,gap_y,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    flag = False


    return img,draw

def template_02(data,finder_patern_number,module_patern,module_color,background_color):

    qr = initial_qr_setup(data)
    matrix,width,height,img,draw = drw_initial_image(qr,background_color)
    flag = True
    gap_x = 0
    gap_y = 0

    drw_border(70,module_color,width, height,draw)
    drw_border(78,background_color,width, height,draw)

    for row in range(height):
        for col in range(width):
            if matrix[row][col] and flag:
                finder_pattern_row = row
                finder_pattern_col = col
                flag = False

    flag = True

    if module_patern == '6':
         drw_line_modules(gap_x,gap_y,height,width,finder_pattern_col,finder_pattern_row,matrix,draw,module_color)
         
    else:
        for row in range(height):
            for col in range(width):
                    if matrix[row][col]:

                        if col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= finder_pattern_row + 6 and row >= finder_pattern_row or col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= height - finder_pattern_row - 1  and row >= height - finder_pattern_row - 7 or row <= finder_pattern_row + 6 and row >= finder_pattern_row and col <= width - finder_pattern_col - 1 and col >= width - finder_pattern_col - 7:
                            continue
                    
                        if module_patern == '1':
                            drw_rectangel(gap_x,gap_y,row,col,False,draw,5,module_color)

                        if module_patern == '2':
                            drw_general_rectangel(gap_x,gap_y,row,col,draw,5,module_color)

                        if module_patern == '3':
                            drw_polygon(gap_x,gap_y,row,col,draw,module_color)

                        if module_patern == '4':
                            drw_circle(gap_x,gap_y,row,col,draw,module_color)

                        if module_patern == '5':
                            drw_triangle(gap_x,gap_y,row, col,draw,5,module_color)

    for row in range(height):
        for col in range(width):
            if matrix[row][col] and flag:
                    if finder_patern_number == '1':
                        drw_finder_patern_01(gap_x,gap_y,row,col,len(matrix[0]), len(matrix),draw,module_color)
                    elif finder_patern_number == '2':
                        drw_finder_patern_02(gap_x,gap_y,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '3':
                       drw_finder_patern_03(gap_x,gap_y,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '4':
                        drw_finder_patern_04(gap_x,gap_y,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    flag = False

    return img,draw

def template_03(data,finder_patern_number,module_patern,module_color,background_color):

    qr = initial_qr_setup(data)
    matrix,width,height,img,draw,circle_start_point_x,circle_start_point_y = drw_initial_round_image(qr,background_color)
    flag = True

    for row in range(height):
        for col in range(width):
            if matrix[row][col] and flag:
                finder_pattern_row = row
                finder_pattern_col = col
                flag = False

    flag = True

    gap_x,gap_y,radius = get_radius_gap(width, height,matrix)
    gap_xt  = gap_x 
    gap_yt  = gap_y 
    avoid_rect = [((finder_pattern_row-1)*10, (finder_pattern_col-1)*10), ((width-finder_pattern_row+1)*10+9, (height-finder_pattern_col+1)*10+9)]
    drw_circle_around_qr(radius,draw, module_color,background_color)
    drw_background_circles(gap_x,gap_y,width, height ,finder_pattern_row, finder_pattern_col,draw,avoid_rect,module_color)

    drw_partial_circle_around_qr(circle_start_point_x,circle_start_point_y,5,draw, width, height, 60, 120,finder_pattern_row,finder_pattern_col,module_color)
    drw_partial_circle_around_qr(circle_start_point_x,circle_start_point_y,5,draw, width, height, 150, 210,finder_pattern_row,finder_pattern_col,module_color)
    drw_partial_circle_around_qr(circle_start_point_x,circle_start_point_y,5,draw, width, height, 240, 300,finder_pattern_row,finder_pattern_col,module_color)
    drw_partial_circle_around_qr(circle_start_point_x,circle_start_point_y,5,draw, width, height, 330, 390,finder_pattern_row,finder_pattern_col,module_color)

    if module_patern == '6':
         drw_line_modules(gap_xt,gap_yt,height,width,finder_pattern_col,finder_pattern_row,matrix,draw,module_color)
         
    else:

        for row in range(height):
            for col in range(width):
                    if matrix[row][col]:
                
                        if col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= finder_pattern_row + 6 and row >= finder_pattern_row or col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= height - finder_pattern_row - 1  and row >= height - finder_pattern_row - 7 or row <= finder_pattern_row + 6 and row >= finder_pattern_row and col <= width - finder_pattern_col - 1 and col >= width - finder_pattern_col - 7:
                            continue


                        if module_patern == '1':
                            drw_rectangel(gap_xt,gap_yt,row,col,False,draw,5,module_color)

                        if module_patern == '2':
                            drw_general_rectangel(gap_xt,gap_yt,row,col,draw,5,module_color)

                        if module_patern == '3':
                            drw_polygon(gap_xt,gap_yt,row,col,draw,module_color)

                        if module_patern == '4':
                            drw_circle(gap_xt,gap_yt,row,col,draw,module_color)

                        if module_patern == '5':
                            drw_triangle(gap_xt,gap_yt,row, col,draw,5,module_color)

    

    for row in range(height):
        for col in range(width):
            if matrix[row][col] and flag:
                    if finder_patern_number == '1':
                        drw_finder_patern_01(gap_xt,gap_yt,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '2':
                        drw_finder_patern_02(gap_xt,gap_yt,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '3':
                       drw_finder_patern_03(gap_xt,gap_yt,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '4':
                        drw_finder_patern_04(gap_xt,gap_yt,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    flag = False

    return img,draw

def template_04(data,finder_patern_number,module_patern,module_color,background_color):

    qr = initial_qr_setup(data)
    matrix,width,height,img,draw,circle_start_point_x,circle_start_point_y = drw_initial_round_image(qr,background_color)
    flag = True

    for row in range(height):
        for col in range(width):
            if matrix[row][col] and flag:
                finder_pattern_row = row
                finder_pattern_col = col
                flag = False

    flag = True

    gap_x,gap_y,radius = get_radius_gap(width, height,matrix)
    gap_xt  = gap_x + 6
    gap_yt  = gap_y + 6
    avoid_rect = [((finder_pattern_row - 1)*10, (finder_pattern_col - 1)*10), ((width-finder_pattern_row + 1)*10+9, (height-finder_pattern_col + 1)*10+9)]
    drw_circle_around_qr(radius,draw, module_color,background_color)
    drw_background_rectangels(gap_x,gap_y,width, height ,finder_pattern_row, finder_pattern_col,draw,avoid_rect,module_color,background_color)

    if module_patern == '6':
         drw_line_modules(gap_xt,gap_yt,height,width,finder_pattern_col,finder_pattern_row,matrix,draw,module_color)
         
    else:
        for row in range(height):
            for col in range(width):
                
                    if col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= finder_pattern_row + 6 and row >= finder_pattern_row or col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= height - finder_pattern_row - 1  and row >= height - finder_pattern_row - 7 or row <= finder_pattern_row + 6 and row >= finder_pattern_row and col <= width - finder_pattern_col - 1 and col >= width - finder_pattern_col - 7:
                        continue

                    if matrix[row][col]:
                    
                        if module_patern == '1':
                            drw_rectangel(gap_xt,gap_yt,row,col,False,draw,5,module_color)

                        if module_patern == '2':
                            drw_general_rectangel(gap_xt,gap_yt,row,col,draw,5,module_color)

                        if module_patern == '3':
                            drw_polygon(gap_xt,gap_yt,row,col,draw,module_color)

                        if module_patern == '4':
                            drw_circle(gap_xt,gap_yt,row,col,draw,module_color)

                        if module_patern == '5':
                            drw_triangle(gap_xt,gap_yt,row, col,draw,5,module_color)

    for row in range(height):
        for col in range(width):
            if matrix[row][col] and flag:
                    if finder_patern_number == '1':
                        drw_finder_patern_01(gap_xt,gap_yt,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '2':
                        drw_finder_patern_02(gap_xt,gap_yt,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '3':
                       drw_finder_patern_03(gap_xt,gap_yt,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '4':
                        drw_finder_patern_04(gap_xt,gap_yt,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    flag = False

    return img,draw

def template_05(data,finder_patern_number,module_patern,module_color,background_color):

    qr = initial_qr_setup(data)
    matrix,width,height,img,draw,circle_start_point_x,circle_start_point_y  = drw_initial_round_image(qr,background_color)
    flag = True

    for row in range(height):
        for col in range(width):
            if matrix[row][col] and flag:
                finder_pattern_row = row
                finder_pattern_col = col
                flag = False

    flag = True

    gap_x,gap_y,radius = get_radius_gap(width, height,matrix)
    avoid_rect = [((finder_pattern_row-1)*10, (finder_pattern_col-1)*10), ((width-finder_pattern_row+1)*10+9, (height-finder_pattern_col+1)*10+9)]
    drw_background_polygon(gap_x,gap_y,width, height ,finder_pattern_row, finder_pattern_col,draw,avoid_rect,module_color)

    drw_partial_circle_around_qr(circle_start_point_x,circle_start_point_y,7,draw, width, height, 60, 120,finder_pattern_row,finder_pattern_col,module_color)
    drw_partial_circle_around_qr(circle_start_point_x,circle_start_point_y,7,draw, width, height, 150, 210,finder_pattern_row,finder_pattern_col,module_color)
    drw_partial_circle_around_qr(circle_start_point_x,circle_start_point_y,7,draw, width, height, 240, 300,finder_pattern_row,finder_pattern_col,module_color)
    drw_partial_circle_around_qr(circle_start_point_x,circle_start_point_y,7,draw, width, height, 330, 390,finder_pattern_row,finder_pattern_col,module_color)

    if module_patern == '6':
         drw_line_modules(gap_x,gap_y,height,width,finder_pattern_col,finder_pattern_row,matrix,draw,module_color)
         
    else:
        for row in range(height):
            for col in range(width):
                if matrix[row][col]:
                
                    if col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= finder_pattern_row + 6 and row >= finder_pattern_row or col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= height - finder_pattern_row - 1  and row >= height - finder_pattern_row - 7 or row <= finder_pattern_row + 6 and row >= finder_pattern_row and col <= width - finder_pattern_col - 1 and col >= width - finder_pattern_col - 7:
                        continue

                    if module_patern == '1':
                        drw_rectangel(gap_x,gap_y,row,col,False,draw,5,module_color)

                    if module_patern == '2':
                        drw_general_rectangel(gap_x,gap_y,row,col,draw,5,module_color)

                    if module_patern == '3':
                        drw_polygon(gap_x,gap_y,row,col,draw,module_color)

                    if module_patern == '4':
                        drw_circle(gap_x,gap_y,row,col,draw,module_color)

                    if module_patern == '5':
                        drw_triangle(gap_x,gap_y,row, col,draw,5,module_color)

    for row in range(height):
        for col in range(width):
            if matrix[row][col] and flag:
                    if finder_patern_number == '1':
                        drw_finder_patern_01(gap_x,gap_y,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '2':
                        drw_finder_patern_02(gap_x,gap_y,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '3':
                       drw_finder_patern_03(gap_x,gap_y,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '4':
                        drw_finder_patern_04(gap_x,gap_y,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    flag = False

    return img,draw

def template_06(data,finder_patern_number,module_patern,module_color,background_color):

    qr = initial_qr_setup(data)
    matrix,width,height,img,draw,circle_start_point_x,circle_start_point_y = drw_initial_round_image(qr,background_color)
    flag = True

    for row in range(height):
        for col in range(width):
            if matrix[row][col] and flag:
                finder_pattern_row = row
                finder_pattern_col = col
                flag = False

    flag = True

    gap_x,gap_y,radius = get_radius_gap(width, height,matrix)
    gap_xt  = gap_x - 4
    gap_yt  = gap_y - 4
    avoid_rect = [((finder_pattern_row-1)*10, (finder_pattern_col-1)*10), ((width-finder_pattern_col+1 )*10, (height-finder_pattern_row+1)*10)]
    drw_circle_around_qr(radius,draw, module_color,background_color)
    drw_background_varius_polygon(gap_x,gap_y,width, height ,finder_pattern_row, finder_pattern_col,draw,avoid_rect,module_color)

    if module_patern == '6':
         drw_line_modules(gap_xt,gap_yt,height,width,finder_pattern_col,finder_pattern_row,matrix,draw,module_color)
         
    else:
        for row in range(height):
            for col in range(width):
                    if matrix[row][col]:
                
                        if col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= finder_pattern_row + 6 and row >= finder_pattern_row or col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= height - finder_pattern_row - 1  and row >= height - finder_pattern_row - 7 or row <= finder_pattern_row + 6 and row >= finder_pattern_row and col <= width - finder_pattern_col - 1 and col >= width - finder_pattern_col - 7:
                            continue
                
                        if module_patern == '1':
                            drw_rectangel(gap_xt,gap_yt,row,col,False,draw,5,module_color)

                        if module_patern == '2':
                            drw_general_rectangel(gap_xt,gap_yt,row,col,draw,5,module_color)

                        if module_patern == '3':
                            drw_polygon(gap_xt,gap_yt,row,col,draw,module_color)

                        if module_patern == '4':
                            drw_circle(gap_xt,gap_yt,row,col,draw,module_color)

                        if module_patern == '5':
                            drw_triangle(gap_xt,gap_yt,row, col,draw,5,module_color)


    for row in range(height):
        for col in range(width):
            if matrix[row][col] and flag:
                    if finder_patern_number == '1':
                        drw_finder_patern_01(gap_xt,gap_yt,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '2':
                        drw_finder_patern_02(gap_xt,gap_yt,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '3':
                       drw_finder_patern_03(gap_xt,gap_yt,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '4':
                        drw_finder_patern_04(gap_xt,gap_yt,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    flag = False

    return img,draw

def template_07(data,finder_patern_number,module_patern,module_color,background_color):

    qr = initial_qr_setup(data)
    matrix,width,height,img,draw,circle_start_point_x,circle_start_point_y = drw_initial_round_image(qr,background_color)
    flag = True

    for row in range(height):
        for col in range(width):
            if matrix[row][col] and flag:
                finder_pattern_row = row
                finder_pattern_col = col
                flag = False

    flag = True

    gap_x,gap_y,radius = get_radius_gap(width, height,matrix)
    avoid_rect = [((finder_pattern_row-1)*10, (finder_pattern_col-1)*10), ((width-finder_pattern_col+1 )*10+9, (height-finder_pattern_row+1)*10+9)]
    drw_background_circles_for_large_circle(gap_x,gap_y,width, height ,finder_pattern_row, finder_pattern_col,draw,avoid_rect,module_color)

    if module_patern == '6':
         drw_line_modules(gap_x,gap_y,height,width,finder_pattern_col,finder_pattern_row,matrix,draw,module_color)
         
    else:
        for row in range(height):
            for col in range(width):
                    if matrix[row][col]:
                
                        if col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= finder_pattern_row + 6 and row >= finder_pattern_row or col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= height - finder_pattern_row - 1  and row >= height - finder_pattern_row - 7 or row <= finder_pattern_row + 6 and row >= finder_pattern_row and col <= width - finder_pattern_col - 1 and col >= width - finder_pattern_col - 7:
                            continue

                        if module_patern == '1':
                            drw_rectangel(gap_x,gap_y,row,col,False,draw,5,module_color)

                        if module_patern == '2':
                            drw_general_rectangel(gap_x,gap_y,row,col,draw,5,module_color)

                        if module_patern == '3':
                            drw_polygon(gap_x,gap_y,row,col,draw,module_color)

                        if module_patern == '4':
                            drw_circle(gap_x,gap_y,row,col,draw,module_color)

                        if module_patern == '5':
                            drw_triangle(gap_x,gap_y,row, col,draw,5,module_color)


    for row in range(height):
        for col in range(width):
            if matrix[row][col] and flag:
                    if finder_patern_number == '1':
                        drw_finder_patern_01(gap_x,gap_y,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '2':
                        drw_finder_patern_02(gap_x,gap_y,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '3':
                       drw_finder_patern_03(gap_x,gap_y,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '4':
                        drw_finder_patern_04(gap_x,gap_y,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    flag = False

    return img,draw

def template_08(data,finder_patern_number,module_patern,module_color,background_color):

    qr = initial_qr_setup(data)
    matrix,width,height,img,draw,circle_start_point_x,circle_start_point_y = drw_initial_round_image(qr,background_color)
    flag = True

    for row in range(height):
        for col in range(width):
            if matrix[row][col] and flag:
                finder_pattern_row = row
                finder_pattern_col = col
                flag = False

    flag = True

    gap_x,gap_y,radius = get_radius_gap(width, height,matrix)
    gap_xt  = gap_x - 4
    gap_yt  = gap_y - 4
    avoid_rect = [((finder_pattern_row-1)*10, (finder_pattern_col-1)*10), ((width-finder_pattern_col+1 )*10, (height-finder_pattern_row+1)*10)]
    drw_circle_around_qr(radius,draw, module_color,'black')
    drw_background_rounded_rectangle(background_color,width, height,draw,finder_pattern_row, finder_pattern_col,gap_xt,gap_yt)

    if module_patern == '6':
         drw_line_modules(gap_xt,gap_yt,height,width,finder_pattern_col,finder_pattern_row,matrix,draw,module_color)
         
    else:
        for row in range(height):
            for col in range(width):
                    if matrix[row][col]:
                
                        if col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= finder_pattern_row + 6 and row >= finder_pattern_row or col <= finder_pattern_col + 6 and col >= finder_pattern_col and row <= height - finder_pattern_row - 1  and row >= height - finder_pattern_row - 7 or row <= finder_pattern_row + 6 and row >= finder_pattern_row and col <= width - finder_pattern_col - 1 and col >= width - finder_pattern_col - 7:
                            continue
                
                        if module_patern == '1':
                            drw_rectangel(gap_xt,gap_yt,row,col,False,draw,5,module_color)

                        if module_patern == '2':
                            drw_general_rectangel(gap_xt,gap_yt,row,col,draw,5,module_color)

                        if module_patern == '3':
                            drw_polygon(gap_xt,gap_yt,row,col,draw,module_color)

                        if module_patern == '4':
                            drw_circle(gap_xt,gap_yt,row,col,draw,module_color)

                        if module_patern == '5':
                            drw_triangle(gap_xt,gap_yt,row, col,draw,5,module_color)


    for row in range(height):
        for col in range(width):
            if matrix[row][col] and flag:
                    if finder_patern_number == '1':
                        drw_finder_patern_01(gap_xt,gap_yt,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '2':
                        drw_finder_patern_02(gap_xt,gap_yt,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '3':
                       drw_finder_patern_03(gap_xt,gap_yt,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    elif finder_patern_number == '4':
                        drw_finder_patern_04(gap_xt,gap_yt,row,col,len(matrix[0]), len(matrix),draw,module_color,background_color)
                    flag = False

    return img,draw


@app.route(route="http_qr", methods=['POST'])
def http_qr(req: func.HttpRequest) -> func.HttpResponse:
    # logging.info('Python HTTP trigger function processed a request.')

    # name = req.params.get('name')
    # if not name:
    #     try:
    #         req_body = req.get_json()
    #     except ValueError:
    #         pass
    #     else:
    #         name = req_body.get('name')

    # if name:
    #     return func.HttpResponse(f"Hello, {name}. This HTTP triggered function executed successfully.")
    # else:
    #     return func.HttpResponse(
    #          "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
    #          status_code=200
    #     )
    data = req.form.get('data')
    data_type = req.form.get('data_type')
    module_color = req.form.get('module_color')
    background_color = req.form.get('background_color')
    module_patern = req.form.get('module_patern')
    template_number = req.form.get('template_number')
    finder_patern_number = req.form.get('finder_patern_number')
    uploaded_image = req.files['filename']

    if uploaded_image:
        if not uploaded_image.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            return func.HttpResponse("Invalid image file format", status_code=400)

        image_data = io.BytesIO(uploaded_image.read())
        image = Image.open(image_data)

    if not background_color:
         background_color = 'white'

    if not module_color:
         module_color = 'black'

    if not (module_patern == '1' or module_patern == '2' or module_patern == '3' or module_patern == '4' or module_patern == '5' or module_patern == '6'):
        return func.HttpResponse("Invalid module pattern", status_code=400)
    
    if not (finder_patern_number == '1' or finder_patern_number == '2' or finder_patern_number == '3' or finder_patern_number == '4'):
        return func.HttpResponse("Invalid finder pattern", status_code=400)

    if data_type == 'weblink':
        data = 'http://' + data if not data.startswith(('http://', 'https://')) else data
    elif data_type == 'email':
        data = 'mailto:' + data
    elif data_type == 'message':
        data = 'sms:' + data
    elif data_type == 'call':
        data = 'tel:' + data
    elif data_type == 'wifi':
        wifi_data = data.split(',')
        if len(wifi_data) == 4:
            ssid, password, encryption, hidden = wifi_data
            data = f'WIFI:S:{quote(ssid)};T:{encryption};P:{quote(password)};H:{hidden};'
        else:
            return func.HttpResponse("Invalid Wi-Fi data format", status_code=400)
    else:
        return func.HttpResponse("Invalid data type", status_code=400)

    qrname = "customize_qr.png"

    if template_number == '1':
        image, draw = template_01(data, finder_patern_number,module_patern,module_color,background_color)
    elif template_number == '2':
        image, draw = template_02(data, finder_patern_number,module_patern,module_color,background_color)
    elif template_number == '3':
        image, draw = template_03(data, finder_patern_number,module_patern,module_color,background_color)
    elif template_number == '4':
        image, draw = template_04(data, finder_patern_number,module_patern,module_color,background_color)
    elif template_number == '5':
        image, draw = template_05(data, finder_patern_number,module_patern,module_color,background_color)
    elif template_number == '6':
        image, draw = template_06(data, finder_patern_number,module_patern,module_color,background_color)
    elif template_number == '7':
        image, draw = template_07(data, finder_patern_number,module_patern,module_color,background_color)
    elif template_number == '8':
        image, draw = template_08(data, finder_patern_number,module_patern,module_color,background_color)
    else:
        return func.HttpResponse("Invalid template", status_code=400)

    if uploaded_image:
        logo = Image.open(image_data)
        resize_logo, pos = add_logo(image, logo)
        draw_large_rectangle_around_image(image.size[0], image.size[1], resize_logo.size[0], resize_logo.size[1], draw,background_color)
        image.paste(resize_logo, pos)
    image_bytes = io.BytesIO()
    image.save(image_bytes, format='PNG')
    name = ''.join(random.choices(string.ascii_lowercase, k=20))
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    blob_name = name+'.png'
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    image_bytes.seek(0)
    blob_client.upload_blob(image_bytes)
    blob_service_client = BlobServiceClient(account_url=f"https://{storage_account_name}.blob.core.windows.net", credential=storage_account_key)

    container_client = blob_service_client.get_container_client(container_name)

    blob_client = container_client.get_blob_client(blob_name)

    download_link = f"https://{storage_account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"
    return func.HttpResponse(download_link, status_code=200)