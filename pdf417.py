#!/usr/bin/env python

from PIL import Image
import itertools
from pdf417dict import codewords_tbl
import sys


# Global variables
val_num = 0
pdf_mode = 'text'
text_submode = 'upper'
text_shift = False

def add_quiet_zone(im):
    box = (15, 15, im.size[0]+15, im.size[1]+15)
    img = Image.new('L', (im.size[0]+30, im.size[1]+30), 'white')
    img.paste(im, box)
    return img


def get_img(img_path):
    return Image.open(img_path)

def print_img_info(im):
    info = im.info
    for item in info.items():
        print item[0], ': ', item[1]
    print 'image mode: ', im.mode
    print 'image size: ', im.size
    print 'file format: ', im.format
    print 'image band: ', im.getbands()
    print 'image box: ', im.getbbox()

def each_row(im, start, end, step=1):
    for y in range(start, end, step):
        yield list(im.crop((2, y, im.size[0]-2, y+1)).getdata())

# not in use
def each_column(im, start, end, step=1):
    for x in range(start, end, step):
        yield list(im.crop((x, 0, x+1, im.size[1])).getdata())

def reformat(row_data):
    return [(i[0], len(list(i[1]))) for i in itertools.groupby(row_data)]


def get_min_width(row):
    return row[1][1]

def row2syms(row, mw):
    return "".join([str(i[1]/mw) for i in row])

def get_cluster(sym):
    return (int(sym[0])-int(sym[2])+int(sym[4])-int(sym[6])+9)%9


pdf417_flag = False
def get_codeword(syms, which):
    global pdf417_flag
    start = which*8-8
    sym = syms[start:start+8]
    if not pdf417_flag:
        if not sym == '81111113':
            return 'access denied'
        pdf417_flag = True
        return 'start'

    if len(syms[start:]) == 9:
        pdf417_flag = False
        return 'end'

    cluster = get_cluster(sym)
    k = cluster/3
    for j in range(0,929):
        if sym == codewords_tbl[k][j]:
            return (k, j)

    return False

def decode_part(part):
    global text_submode, text_shift

    text_dict = {
        'upper': "ABCDEFGHIJKLMNOPQRSTUVWXYZ    ",
        'lower': "abcdefghijklmnopqrstuvwxyz    ",
        'mixed': "0123456789&\r\t,:#-.$/+%*=^     ",
        'punct': ";<>@[\\]_`~!\r\t,:\n-.$/\"|*()?{}' "
    }

    ret = 'unknown'
    if text_submode == 'upper':
        if part == 27:
            text_submode = 'lower'
            return 'll'
        elif part == 28:
            text_submode = 'mixed'
            return 'ml'
        elif part == 29:
            text_shift =  'punct'
            return 'ps'
        else:
            if text_shift:
                ret = text_dict[text_shift][part]
                text_shift = False
            else:
                ret = text_dict[text_submode][part]
            return ret

    elif text_submode == 'lower':
        if part == 27:
            text_shift = 'upper'
            return 'as'
        elif part == 28:
            text_submode = 'mixed'
            return 'ml'
        elif part == 29:
            text_shift = 'punct'
            return 'ps'
        else:
            if text_shift:
                ret = text_dict[text_shift][part]
                text_shift = False
            else:
                ret = text_dict[text_submode][part]
            return ret

    elif text_submode == 'mixed':
        if part == 25:
            text_submode = 'punct'
            return 'pl'
        elif part == 27:
            text_submode = 'lower'
            return 'll'
        elif part == 28:
            text_submode = 'upper'
            return 'al'
        elif part == 29:
            text_shift = 'punct'
            return 'ps'
        else:
            if text_shift:
                ret = text_dict[text_shift][part]
                text_shift = False
            else:
                ret = text_dict[text_submode][part]
            return ret

    elif text_submode == 'punct':
        if part == 29:
            text_submode = 'upper'
            return 'al'
        else:
            if text_shift:
                ret = text_dict[text_shift][part]
                text_shift = False
            else:
                ret = text_dict[text_submode][part]
            return ret

    else:
        return 'Error'


def decode_cw(cw):
    global pdf_mode, val_num, text_submode, text_shift

    if cw == 900:
        pdf_mode = 'text'
        text_submode = 'upper'
        text_shift = False
        if val_num > 0:
            val = val_num
            val_num = 0
            num_str = '%d' % val
            return (num_str[1:], '')
        else:
            return ''
    elif cw == 902:
        pdf_mode = 'num'
        return ''
    elif cw >= 903:
        return ''
    else:
        if pdf_mode == 'text':
            return decode_text(cw)
        elif pdf_mode == 'num':
            decode_number(cw)
            return ''


def decode_text(cw):
    H = cw/30
    L = cw%30

    return (decode_part(H), decode_part(L))


def decode_number(cw):
    global val_num
    val_num *= 900
    val_num += cw


def get_cwinfo(codewords):
    l1 = codewords[0][0]
    l2 = codewords[1][0]
    l3 = codewords[2][0]
    length = len(codewords)
    z = l2%30
    v = l3%30
    error_level = (z - (length-1)%3)/3
    num_of_rows = v+1
    return dict({'error_level':error_level, 'num_of_rows':num_of_rows})

def filter_quitezone(row_data):
    if row_data[0][0] == 255:  row_data = row_data[1:]
    if row_data[-1][0] == 255: row_data = row_data[0:-1]
    return row_data

def filter_se_pattern(cw_of_row):
    return [i[1] for i in cw_of_row[1:-1]]

def filter_err(codewords_list, error_level):
    return codewords_list[:-2**(error_level+1)]

def filter_row_indicator(codewords):
    return [k for i in codewords for k in i[1:-1]]

def get_content(codewords):
    skip = ['ll', 'ps', 'ml', 'al', 'pl', 'as']
    return "".join( [str(k) for i in codewords for k in i if k not in skip] )

def _reset_global_vars():
    global text_shift, text_submode, pdf417_flag
    text_shift = False
    text_submode = "upper"
    pdf417_flag = False

        
def pdf417_decode(img_path):
    mw = 0 # min-width of the barcode
    codewords = []
    im = add_quiet_zone(get_img(img_path))
    im_h = im.size[1]
    target = im.convert('L')
    #print_img_info(target)
    
    for arow in each_row(target, 0, im_h):
        cw_of_row = []
        tmp_row = reformat(arow)
        #print 'Row: ', tmp_row
        if len(tmp_row) == 1:
            continue

        row = filter_quitezone(tmp_row)
        if not mw:
            mw = get_min_width(row)

        syms = row2syms(row, mw)
        #print 'Syms: ', syms
        end = len(syms)/8+1
        for i in range(1, end):
            sym = get_codeword(syms, i)
            cw_of_row.append(sym)

        cw_of_row = filter_se_pattern(cw_of_row)
        if cw_of_row not in codewords:
            codewords.append(cw_of_row)

    info =  get_cwinfo(codewords)
    codewords_list = [cw for row in codewords for cw in row[1:-1]]
    codewords_noerr = filter_err(codewords_list, info['error_level'])

    vals = [decode_cw(cw) for cw in codewords_noerr]
    _reset_global_vars()

    # print "*" * 80
    # print "found the codewords:", codewords
    # print "*" * 80
    # print "data codewords:",codewords_list
    # print "*" * 80
    # print "codewords without error message :", codewords_noerr
    # print "*" * 80
    # print "found ascii text index:", vals
    # print "*" * 80
    # print get_content(vals)
    # print "*" * 80
    # print "*" * 80

    return get_content(vals)[1:]


if __name__ == '__main__':
    ret = pdf417_decode(sys.argv[1])
    print ret
