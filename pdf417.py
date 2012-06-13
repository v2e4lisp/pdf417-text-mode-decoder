from PIL import Image
import itertools
from pdf417dict import codewords_tbl

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

text_submode = 'upper'
text_shift = False
def decode_text(cw):
    if cw >= 900:
        return ''
    H = cw/30
    L = cw%30
    upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ    ";
    lower = "abcdefghijklmnopqrstuvwxyz    ";
    mixed = "0123456789&\r\t,:#-.$/+%*=^     ";
    punct = ";<>@[\\]_`~!\r\t,:\n-.$/\"|*()?{}' ";
    text_dict = {'upper':upper, 'lower':lower,
                 'mixed':mixed, 'punct':punct}

    def decode_part(part):
        global text_submode, text_shift
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

    return (decode_part(H), decode_part(L))
    
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
    im = get_img(img_path)
    im_h = im.size[1]
    target = im.convert('L')
    # print_img_info(target)
    
    for arow in each_row(target, 0, im_h):
        cw_of_row = []
        tmp_row = reformat(arow)
        if len(tmp_row) == 1:
            continue

        row = filter_quitezone(tmp_row)
        if not mw:
            mw = get_min_width(row)

        syms = row2syms(row, mw)
        end = len(syms)/8+1
        for i in range(1, end):
            sym = get_codeword(syms, i)
            cw_of_row.append(sym)

        cw_of_row = filter_se_pattern(cw_of_row)
        if cw_of_row not in codewords:
            codewords.append(cw_of_row)

    info =  get_cwinfo(codewords)
    codewords_list = filter_row_indicator(codewords)
    codewords_noerr = filter_err(codewords_list, info['error_level'])
    vals = [decode_text(i) for i in codewords_noerr]
    _reset_global_vars()

    print "*" * 80
    print "found the codewords:", codewords
    print "*" * 80
    print "data codewords:",codewords_list
    print "*" * 80
    print "codewords without error message :", codewords_noerr
    print "*" * 80
    print "found ascii text index:", vals
    print "*" * 80
    print "contents:", get_content(vals)
    print "*" * 80
    print "*" * 80


if __name__ == '__main__':
    pdf417_decode("/home/jinseyaluji/Pictures/123456789.gif")
    pdf417_decode("/home/jinseyaluji/Pictures/PDF417.png")
