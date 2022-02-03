#!/usr/bin/python
# -*- coding: utf-8
# TODO: mnozne cislo (books->book,  kisses->kiss, fries->fry),  3. osoba (plays->play,  cries->cry)
# TODO: Preklad - done
# TODO: Odstranit duplikaty ve vyslovnosti - done
# TODO: Zaskrtavaci policka na americkou a britskou vyslovnost -  done
# TODO: Pokud je vic Entries,  tak u kazdeho vyslovnost
# TODO: Checkbox for translations - done
# TODO: Moznost otevrit vsechna slovicka ve slovniku,  viz priklad z Nachsclagen - done
# TODO: Přidat dole etymologii a pokud existuje,  tak register + zvážit změnu pořádí noun,  adjective... done
# TODO: settings window
import json
import threading
import sys
import os
import io
import re
from aqt import *
import time
import pickle
import threading
try:
    import urllib2
except ImportError:
    import urllib.request as urllib2
try:
    import requests
    req_found = True
except ImportError:
    req_found = False
gnudict = None
trans_loaded = False


class Timer:

    def __init__(self):
        self.start = time.time()
        self.last = self.start
        self.times = []

    def __call__(self, text):
        now = time.time()
        self.times.append((text, now-self.start, now-self.last))
        # print2("Elapsed time: total {0},  dif {1}", now-self.start, now-self.last)
        self.last = now

    def save_results(self):
        with io.open("timer.txt", "w") as file:
            for text, total, dif in self.times:
                file.write(u"{0}: total  =  {1},  dif  = {2}\n".format(text, total, dif))

    def reset(self):
        self.start = time.time()
        self.last = self.start


timer = Timer()
app_id = "fill_your_own_id"
app_key = "fill_your_own_key"
headers = {"app_id": app_id, "app_key": app_key}
button_clicked = False
wlim = 50


def print2(*args):
    text = " ".join(map(str, args))
    return aqt.utils.showInfo(text)


# print2 = print
hyperlink = True
PREFL = len("http://audio.oxforddictionaries.com/")
audio_list = []


def parse_json(text):
    try:
        parsed = json.loads(text)
    except ValueError:
        return False
    return parsed


def get_examples(result):
    examples = []
    for l_en in result["lexicalEntries"]:
        new_ex = []
        for sense in l_en["entries"][0]["senses"]:

            if "examples" in sense:
                
                for ex in sense["examples"]:
                    new_ex.append(ex["text"])
                examples.append(new_ex)
        examples.append(new_ex)
    return examples


def get_defintions(result):
    
    #definitions = [[el["definitions"] for el in sel["entries"][0]["senses"]] for sel in parsed["results"][0]["lexicalEntries"]]
    definitions = []
    for sel in result["lexicalEntries"]:
        new_def = []
        
        for el in sel["entries"][0]["senses"]:
            new_def.append((el["definitions"]))
            
        definitions.append(new_def)
    return definitions


def get_prons(result):
    vocab = result["id"]
    prons = []
    
    for l_en in result["lexicalEntries"]:
        
        if "pronunciations" in l_en:
            
            prons.append([(pron["phoneticSpelling"] if ("phoneticSpelling" in pron and "phoneticNotation" in pron and pron["phoneticNotation"] == "IPA") else "" , pron["audioFile"] if "audioFile" in pron else "") for pron in l_en["pronunciations"]])
        elif "entries" in  l_en:
            if "pronunciations" in l_en["entries"][0]:
                prons.append([(pron["phoneticSpelling"] if ("phoneticSpelling" in pron and "phoneticNotation" in pron and pron["phoneticNotation"] == "IPA") else "" , pron["audioFile"] if "audioFile" in pron else "") for pron in l_en["entries"][0]["pronunciations"]])
            else :
                prons.append([["", ""]])
    return prons


def w_filter(string):
    ret = string.capitalize()
    ret = ret.replace("\n", "<br>")
    return ret


def download_mp3_threaded(link): 
    
    #("Inside download_mp3_threaded,  link =  {0}".format(link))
    
    try:
        file = urllib2.urlopen(link)
        fname = link[PREFL:].replace('/', '_')
        with io.open(fname, "wb") as mp3file:
            mp3file.write(file.read())
        #print2("Success!")
    except Exception as err:
        pass#print2("Error!")
        #print2("Error downloading audio file '"+link+"': "+err)


def highlight_mod(text, word, ignore_case=True, symbols=["*", "*"]): 
    text = re.sub("([^A-z]*)(.)(.*)", lambda s: s.group(1)+s.group(2).upper()+s.group(3), text)
    ex = reg_highlight(text, word, ignore_case, symbols)
    if (word[-2:] == "ie"):
        ex = reg_highlight(ex, word[:-2]+"ying", ignore_case, symbols)
    else:
        if (word[-1] == "y"):
            ex = reg_highlight(ex, word[:-1]+"ies", ignore_case, symbols)
            ex = reg_highlight(ex, word[:-1]+"ied", ignore_case, symbols)
        ex = reg_highlight(ex, word[:-1]+"ing", ignore_case, symbols)
    
    
    return ex


def highlight(s, p, ignore_case=True, symbols=["*", "*"]):        
    def find_all(s, p, ignore_case=True):
        '''Yields all the positions of
        the pattern p in the string s.'''
        if ignore_case:
            s = s.lower()
            p = p.lower()
        i = s.find(p)
        while i != -1:
            yield i
            i = s.find(p,  i+1)
    ns = s
    symb_len = len(symbols[0]+symbols[1])
    for i, ind in enumerate(find_all(s, p, ignore_case)):
        kind = ind+i*(symb_len)
        ns = ns[:kind]+symbols[0]+ns[kind:kind+len(p)]+symbols[1]+ns[kind+len(p):]
    symb0_len = len(symbols[0])
    if ns[:symb0_len] == symbols[0]:
        
        return ns[:symb0_len]+ns[symb0_len:].capitalize()
    else:
        return ns.capitalize()


def reg_highlight(text, p, ignore_case=True, symbols=["*", "*"]):
    
    if ignore_case:
        return re.sub("((?i){0})".format(p), lambda s: symbols[0]+s.group(0)+symbols[1], text)    
    else:
        return re.sub("({0})".format(p), lambda s: symbols[0]+s.group(0)+symbols[1], text)    


def get_all(result):
    
    definitions = []
    examples = []
    categories = []
    prons = []
    registers = []
    etymologies = []
    pronunciations = get_prons(result)
    for l_en in result["lexicalEntries"]:
        cat_ex = []
        cat_def = []
        cat_prons = []
        cat_regs = []
        try:
            for etym in l_en["entries"][0]["etymologies"]:
                etymologies.append([etym for etym in l_en["entries"][0]["etymologies"]])
        except KeyError:
            etymologies.append(None)
        for sense in l_en["entries"][0]["senses"]:
            
            
            try:
                cat_regs.append(sense["registers"])
                   
            except KeyError:
                cat_regs.append(None)
                    
            
            sense_ex = []
            if "examples"  in sense:
                for ex in sense["examples"]:
                    sense_ex.append(ex["text"])
            
            sub_def = []
            sub_ex = []
            if "subsenses" in sense:
                
                for subs in sense["subsenses"]:
                     
                    if "definitions" in subs: 
                        defkey = "definitions"
                    else: #elif "crossReferenceMarkers" in subs:
                        defkey = "crossReferenceMarkers"
                    sub_def.append(subs[defkey])
                    #else:
                    #    continue
                    
                    low_ex = []
                    if "examples"  in subs:
                        for ex in subs["examples"]:
                            low_ex.append(ex["text"])
                            #sub_ex.append(ex["text"])
                    sub_ex.append(low_ex)    
            #print('\nsense:\n', sense)
            if "definitions" in sense: 
                defkey = "definitions"
            else: #elif "crossReferenceMarkers" in subs:
                defkey = "crossReferenceMarkers"
            cat_def.append([sense[defkey], sub_def])
            
            cat_ex.append([sense_ex, sub_ex])
                
        categories.append(l_en["lexicalCategory"]["text"])
        definitions.append(cat_def)
        registers.append(cat_regs)
        examples.append(cat_ex)
        
    return (definitions, examples, categories, pronunciations, registers, etymologies)


def get_translations(wlist):
    global gnudict
    global trans_loaded
    #print2("pickle" if gnudict is not None else "None")
    if gnudict is not None and trans_loaded == True:
        return [gnudict.get(re.sub("_", " ", word), []) for word in wlist]
    else:
        
        return get_translations2(wlist)


def get_translations2(wlist):
    import io
    #print2("Translation file gnudict.pickle not found! Falling back to gnudict.txt")
    trans_file = "gnudict.txt"
    try:
        with io.open("../../addons21/VocabDownloader/"+trans_file, encoding = "utf-8") as dictfile:
            text = dictfile.read()
            trans = [re.findall(r"^{0}\s*\t(.*?)\t".format(re.sub("_", " ", word)), text, re.MULTILINE) for word in wlist]
        return trans
    except IOError as err:
        print2("Translation file "+trans_file+" not found! No translations will be provided")#+str(err)+"|"+os.path.dirname(__file__))
        return [[] for word in wlist]

    
def CreateImportList(wordlist, from_lang="British English", include_translations=True, include_mp3=True):
    
    if from_lang == "American English":
        language = "en-us"
    elif from_lang == "Espa"+u"\u00F1"+"ol":
        language = "es"
    else:
        language = "en-gb"
    timer("CreateImportList")
    sw = [] #Sucesfully words
    erw = [] #Words for which error occured
    if len(wordlist)>wlim:
        print2("The number of words exceeds the limit ("+str(len(wlist))+"/"+str(limit)+")")        
        return [[], [wordlist]]                     
    
    afname = "Import_list.txt"
    io.open(afname, "w", encoding = "utf-8").close()

    timer("Translations")
    if (include_translations == True):
        translations = get_translations(wordlist)
    else:
        translations = [[] for word in wordlist]
    timer("Zacatek prochazeni slov")
    
    def download_dict_data(reslist, wind, word):
            
            
        word_id  =  word
        url  =  "https://od-api.oxforddictionaries.com/api/v2/entries/" + language + "/" + word_id.lower()
        
        timer("Stahovani dat")
        if req_found:
            
            try:
                request = requests.get(url, headers=headers)
                text = request.text
                reslist.append((wind, text))
                #request.raise_for_status()
            except requests.exceptions.HTTPError as err:
                reslist.append((wind, None))   
                erw.append([word, "Error downloading data for word '"+re.sub("_"," ",word)+"': "+str(err)])
            except Exception as e:
                reslist.append((wind, e))
                    #sys.exit()
            
            
        else:
            request = urllib2.Request(url)
            for key, value in headers.items():
                request.add_header(key, value) 
            try:
                #print2(url)
                request = urllib2.urlopen(request)
                text = request.read().decode("utf-8")
                reslist.append((wind, text))
            except urllib2.HTTPError as err:
                reslist.append((wind, None))   
                err_message = err.read()
                if "No entry found matching supplied source_lang,  word and provided filters" in err_message:
                    err_message = " The word not found"
                erw.append([word, "Error downloading data for word '"+re.sub("_"," ",word)+"': "+err_message])
                
            except Exception as e:
                reslist.append((wind, e))
            finally:
                pass
                #print2("Processed word #", wind, word)
    #q = queue.Queue()
    res_list = []
    threads = [threading.Thread(target = download_dict_data, args = [res_list, wind, word]) for wind, word in enumerate(wordlist)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout = 30)
    try:
        assert len(res_list) == len(wordlist)
    except AssertionError as ae:
        print2("Nesedi pocet slov a pocet vysledku!")
        raise ae
    res_list = sorted(res_list)
    for wind, r in res_list:
        if isinstance(r, Exception):
            raise r
    for wind, word in enumerate(wordlist):    
        #file = io.open(vocab+"_source.txt", "w", encoding = "utf-8")
        
        #file.write(text)
        #file.close()
        #print(request)
        
        text = res_list[wind][1]
        if text == None:
            continue
        timer("Parsovani stazenych dat")
        parsed = parse_json(text)
        if parsed == False:
            #print2("Error downloading word '"+word+"',  status code: "+request.status_code)
            erw.append([word, "Error downloading word '"+word+"',  status code: "+request.status_code])
            continue                    
        elif "error" in parsed:
            # print2(u"Couldn't find word '"+word+"',  status code: "+request.status_code)
            erw.append([word, u"Couldn't find word '"+word+"',  status code: "+request.status_code])
            continue                    
        else:
            if "results" not in parsed:
              # print2("The entry for '"+word+"' doesn't contain any results!")
               erw.append([word, "The entry for '"+word+"' doesn't contain any results!"])
               continue                    
            else:
                res = parsed["results"]                
                if len(res) == 0:
                    #print2("No result found for '"+word+"'!")
                    erw.append([word, "No result found for '"+word+"'!"])
                    continue                    
                try:    
                    CreateImportEntry(res, word, afname, translations[wind], include_mp3)
                except IOError as e:
              #      print2(u"Error processing results for word '"+word+"': "+e.read())
                    erw.append([word, u"Error writing to the import file for word '"+word+"': "+str(e)])
                    continue                    
                #except Exception as e:
                #    print2("Error processing results for word '"+word+"': "+str(e))
                #    raise e
        sw.append(word)            
        aqt.mw.progress.update(label = "Processing words", value = wind+1)
    return [sw, erw]


def CreateImportEntry(parsed, vocab, afname, trans, include_mp3):
        
    timer("CreateImportEntry for {0}".format(vocab))
    with io.open(afname, "a", encoding = "utf-8") as parsed_file:
        sep_symbol = u"@"
        res_seperator = u"<hr style = 'height:2px; color:blue'>"
        d_all = [];e_all = [];c_all = [];p_all = [];reg_all = [];etym_all = []
        collect_sense_subex_all = []
        collect_cat_subex_all = []
        collect_all_subex_all = []
        collect_cat_ex_all = []
        collect_cat_allex_all = []
        pronunciations_all = []
        for result in parsed: 
            timer("CreateImportEntry: get_all for {0}".format(vocab))

            d, e, c, p, r, etym = get_all(result)
            #print(d)
            d_all.append(d);e_all.append(e);c_all.append(c);p_all.append(p);reg_all.append(r);etym_all.append(etym)
            collect_sense_subex_all.append([[[el  for fel in s_ex[1] for el in fel] for s_ex in cat_ex ] for cat_ex in e ])
            collect_cat_subex_all.append([[pel  for el in cat_ex for pel in el ]  for cat_ex in collect_sense_subex_all[-1]])
            collect_all_subex_all.append([el for fel in collect_cat_subex_all[-1] for el in fel] )
            collect_cat_ex_all.append([[pel for el in cat_ex for pel in el[0] ]  for cat_ex in e])
            pronunciations_all.append(p)
        
            collect_cat_allex = []
            for cat_ex in e:
                new_ex = []
                for sense_ex in cat_ex:
                    new_ex += [ex for ex in sense_ex[0]]
                    new_ex += [ss_ex for s_ex in sense_ex[1] for ss_ex in s_ex]
                    #for ex in sense_ex[0]:
                    #    new_ex.append(ex)
                   # for s_ex in sense_ex[1]:
                    #    for ss_ex in s_ex:
                     #       new_ex.append(ss_ex)
                collect_cat_allex.append(new_ex)
            collect_cat_allex_all.append(collect_cat_allex)
        #print(collect_cat_ex)
        #print(exam)
        space = u"&nbsp"
        tab = space*4
        fvoc = w_filter(vocab).replace("_", " ")
        timer("CreateImportEntry: zapisovani do souboru pro {0}".format(vocab))

        if hyperlink:
            parsed_file.write(u"<a href='https://dictionary.cambridge.org/dictionary/english/"+fvoc+"' style='text-decoration: none'>"+fvoc+"</a>"+sep_symbol)
        else:
            parsed_file.write(fvoc+sep_symbol)
        entrynum = len(parsed)
        lal1=u'<div style=" text-align: left">'
        lal2 = u'</div>'
        for rind, result in enumerate(parsed):  #definice
            if entrynum>1:
                parsed_file.write(u'<div style="color:blue;font-size:45px ; text-align: left">Entry '+str(rind+1)+"/"+str(entrynum)+"</div>") 
                parsed_file.write(u"<div style='font-size:30px'>"+" "+"</div>")
            for ind, cat in enumerate(c_all[rind]):
                
                parsed_file.write(lal1+"<span style='color: rgb(255,99,71)'><i>{0}</i></span>".format(w_filter(cat))+lal2)
                parsed_file.write(u"<div style='font-size:10px'>"+space+"</div>")

                for sind, sense in enumerate(d_all[rind][ind]) :
                    #parsed_file.write(lal1+str(sind+  1)+" ")
                    #parsed_file.write(u"<br>") 
                    #print(sense)
                    
                    for s in sense[0]:
                        
                        #parsed_file.write(u"<b>(<i>"+w_filter(cat)+"</i>)"+" "+w_filter(s)+"</b>"+lal2)
                        if reg_all[rind][ind][sind] == None:
                            parsed_file.write(lal1+str(sind+  1)+" <b>"+w_filter(s)+"</b>"+lal2)
                        else:
                            reg_string = ""
                            for regind, reg in enumerate(reg_all[rind][ind][sind]):
                                try:
                                    
                                    if regind>0: reg_string += ",  " ;
                                    
                                    reg_string += reg["id"]
                                    
                                except KeyError:
                                    pass
                            reg_string="<span style='color: gray'><i>{0}</i></span>".format(reg_string)
                            parsed_file.write(lal1+str(sind+  1)+" "+reg_string+" <b>"+w_filter(s)+"</b>"+lal2)
                        
                        #parsed_file.write(u"<div style = 'font-size:25px'>"+" "+"</div>")
                        for ssind, subsense in enumerate(sense[1]):
                            #parsed_file.write(tab+len("Subsenses:")*" "+chr(ord('a')+ssind)+": ")
                            parsed_file.write(u"<div style='font-size:25px;text-align:left'>"+tab+str(sind+1)+'.'+chr(ord('a')+ssind)+space)
                            for ss in subsense:
                                parsed_file.write(w_filter(ss)+"</div>")    
                        parsed_file.write(u"<div style='font-size:25px'>"+space+"</div>")
            if (rind<len(parsed)-1 and len(parsed)>1):
                parsed_file.write(res_seperator)

                
        parsed_file.write(sep_symbol)
        for rind, result in enumerate(parsed):
            for ind, cat in enumerate(c_all[rind]):
                for ex in collect_cat_allex_all[rind][ind]:
                    ex=highlight_mod(ex,fvoc,ignore_case=True,symbols=['<span style="color:red;">',"</span>"])
                    
                    parsed_file.write(u"<div text-align = center>"+ex.replace("\n", "<br>")+"</div>")  
                    parsed_file.write(u"<div style='font-size:15px'>"+space+"</div>")

                if (rind<len(parsed)-1 and len(parsed)>1):
                    parsed_file.write(res_seperator)
                    
        parsed_file.write(sep_symbol)
        
        for rind, result in enumerate(parsed):
            used  =  set()
            
            for ind, cat in enumerate(c_all[rind]):
                upron = [x[0] for x in pronunciations_all[rind][ind] if x[0] not in used and (used.add(x[0]) or True)]    
                #for el in used:
                 #   print2("used: "+el)
                for pron in upron:
                #for pron in pronunciations_all[rind][ind]
                    if len(pron)>0:
                        parsed_file.write(u"["+pron+"]")
                    
            if (rind<len(parsed)-1 and len(parsed)>1):
                
                if all(len(p_p[0]) == 0 for p_cat in pronunciations_all[rind+1] for p_p in p_cat ):
                    pass
                else:
                    parsed_file.write(res_seperator)
        parsed_file.write(sep_symbol)
        parsed_file.write(u"<div style='text-align: left'>")
        for t_ind, tword in enumerate(trans):
            if t_ind == 0:
                parsed_file.write(tword.capitalize())
            else:
                parsed_file.write(tword)
            if t_ind<len(trans)-1:
                parsed_file.write(u", "+" ")
            
        parsed_file.write(u"</div>")
        parsed_file.write(sep_symbol)
        if include_mp3: #Trva to totiz dlouho
            for rind, result in enumerate(parsed):
                used  =  set()
                for ind, cat in enumerate(c_all[rind]):
                    uaudio = [x[1] for x in pronunciations_all[rind][ind] if (not (x[1] == "") and (x[1] not in used) and (used.add(x[1]) or True))]    
                    for audio in uaudio:
                        #mp3name, dl_success = download_mp3(audio)
                        mp3name = audio[PREFL:].replace('/', '_')
                        audio_list.append(audio)
                            #parsed_file.write("["+pron[1]+"]")
                        #if dl_success:
                        parsed_file.write(u"[sound:"+mp3name+"]")
                            
                        
                #if (rind<len(parsed)-1 and len(parsed)>1):
                 #   parsed_file.write(res_seperator)
            #parsed_file.write(sep_symbol)
                
        parsed_file.write(sep_symbol)
        for et_list_list in etym_all:            
            for et_list in et_list_list:
                if et_list is not None:
                    for et in et_list:
                        parsed_file.write(lal1+et+lal2)    
                        parsed_file.write(u"<br>")    
                            

                
        #parsed_file.write(sep_symbol)
        
        parsed_file.write(u"\n")
            



def threads_download_mp3s():
    
    global audio_list
    threads = [threading.Thread(target = download_mp3_threaded, args = (audio, ) ) for audio in audio_list]
    audio_list = []
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

        
class IBox:


    def __init__(self):
        from aqt import mw
        self.show_tooltips = True
        self.add_translation = True
        self.add_audio = True
        self.lookup_dictionary = "Cambridge"
        self.czech_dictionary = "Lingea.cz"
        self.langs = ["British English", "American English"]#, "Espa"+u"\u00F1"+"ol"]
        self.def_lang = "British English"
        self.widget_collection = []
        try:
            with open("../../addons21/VocabDownloader/VDsettings.json", "r") as settings_file:
                import json
                try:
                    settings = json.loads(settings_file.read())
                    if type(settings) == dict:
                        if "def_lang" in settings and settings["def_lang"] in self.langs:
                            self.def_lang = settings["def_lang"]
                        if "show_tooltips" in settings :
                            self.show_tooltips = settings["show_tooltips"]
                        if "add_audio" in settings:
                            self.add_audio = settings["add_audio"]
                        if "pridat_preklad" in settings:
                            self.add_translation = settings["pridat_preklad"]
                        if "lookup_dictionary" in settings:
                            self.lookup_dictionary = settings["lookup_dictionary"]
                        if "cesky_slovnik" in settings:
                            self.czech_dictionary = settings["cesky_slovnik"]
                except ValueError:#json.decoder.JSONDecodeError:
                    print2("Wrong formatting in file "+os.path.join(os.path.dirname(__file__), 'VDsettings.txt')+". Please edit or remove the file")
                    pass
        except IOError:
            pass            
        mw.myWidget  =  self.pw  =  QLabel()#(None, Qt.WindowMinMaxButtonsHint | Qt.WindowContextHelpButtonHint)
        #self.settings_window(w)
        #w.setWindowFlags( Qt.WindowContextHelpButtonHint |  Qt.WindowMinMaxButtonsHint)
        #mw.myWidget  =  w  =  QDialog()
        self.pw.setWindowTitle("Vocabulary Importer Plugin")
        #self.pw.setGeometry(20,  20,  540,  640)
        #screenRect = self.pw.window().windowHandle().
        self.pw.setStyleSheet("""QToolTip { 
                            
                            border: black solid 1px
                            }""")
        #self.pw.setGeometry(200,  200,  650,  650)
        geom = mw.frameGeometry()
        self.pw.setGeometry(geom.x()+geom.width()/9,  geom.y()+2.7*geom.height()/10,  4*geom.width()/12,  6*geom.height()/12) 
        #print2(str(y.width())+", "+str(y.height()))
        self.input_label  =  QLabel("Insert new words here:")
        #self.input_label.setToolTip("You can also type in whole sentences. The words will get extracted.")
        self.input_box = QPlainTextEdit()
        layout = QVBoxLayout(self.pw)
        blayout = QHBoxLayout(self.pw)
        upperHlayout = QHBoxLayout(self.pw)
        self.cambridge_button = QPushButton("&Search in {0} dictionary".format(self.lookup_dictionary))
        self.lingea_button = QPushButton(u"Hleda&t na {0}".format(self.czech_dictionary))
        upperHlayout.addWidget(self.input_label, 60)
        upperHlayout.addWidget(self.cambridge_button, 20)
        upperHlayout.addWidget(self.lingea_button, 20)
        layout.addLayout(upperHlayout)
        
        layout.addWidget(self.input_box)
        self.import_button  =  QPushButton("&Import")
        
        self.load_file_button = QPushButton("&Load from file")
        close_button = QPushButton("Clos&e")
        self.input_box.setFocus()
        
        self.cambridge_button.clicked.connect(lambda dic: self.search_dic(self.lookup_dictionary))  
        self.cambridge_button.setShortcut(QKeySequence("Ctrl+s"))
        self.lingea_button.clicked.connect(lambda dic: self.search_dic(self.czech_dictionary))  
        self.lingea_button.setShortcut(QKeySequence("Ctrl+t"))
        self.import_button.clicked.connect(self.on_import_click)  
        self.load_file_button.clicked.connect(self.load_file_click)
        
        import_ctrl_i = QAction(self.pw, triggered = self.import_button.animateClick)#(self,  triggered = find_next_btn.animateClick)
        import_ctrl_i.setShortcut(QKeySequence("Ctrl+I"))
        import_ctrl_enter = QAction(self.pw, triggered = self.import_button.animateClick)#(self,  triggered = find_next_btn.animateClick)
        import_ctrl_enter.setShortcut(QKeySequence("Ctrl+Return"))
        #self.import_button.setShortcut(QKeySequence("Ctrl+I"))
        
        self.load_file_button.setShortcut(QKeySequence("Ctrl+l"))
        
        close_ctrl_e = QAction(self.pw, triggered = close_button.animateClick)#(self,  triggered = find_next_btn.animateClick)
        close_ctrl_e.setShortcut(QKeySequence("Ctrl+E"))
        close_esc = QAction(self.pw, triggered = close_button.animateClick)#(self,  triggered = find_next_btn.animateClick)
        close_esc.setShortcut(QKeySequence("Esc"))
        self.pw.addActions([close_ctrl_e, close_esc, import_ctrl_i, import_ctrl_enter])
        close_button.clicked.connect(self.close_window)
        blayout.addWidget(self.import_button)
        blayout.addWidget(self.load_file_button)
        blayout.addWidget(close_button)
        lang_layout  =  QHBoxLayout()
        self.from_box  =  QComboBox()
        self.from_box.addItems(self.langs)
        self.from_box.setCurrentIndex(self.langs.index(self.def_lang))
        lang_layout.addWidget(self.from_box)
        #close_ctrl_e.setShortcutContext(Qt.ApplicationShortcut);
        #close_ctrl_e.setShortcutVisibleInContextMenu(True)
        
        self.audio_checkbox = QCheckBox("Include au&dio")
        
        self.audio_checkbox.setShortcut(QKeySequence("Ctrl+d"))
        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self.settings_window)
        lang_layout.addWidget(self.audio_checkbox)
        #self.t_checkbox = QCheckBox(u"Přidat &překlad")
        self.t_checkbox = QCheckBox(u"Přidat &překlad")
        if self.add_audio:
            self.audio_checkbox.setChecked(True)
        if self.add_translation:
            self.t_checkbox.setChecked(True)
        self.t_checkbox.setShortcut(QKeySequence("Ctrl+p"))
        
        lang_layout.addWidget(self.t_checkbox)
        #lang_layout.addWidget(self.settings_button)
        layout.addLayout(lang_layout)
        layout.addLayout(blayout)
        
        if self.show_tooltips:
           self.setup_tooltips()
        self.widget_collection.extend([self.input_box, self.input_label, self.import_button, self.load_file_button, self.cambridge_button, self.lingea_button, self.t_checkbox, 
        self.audio_checkbox])
        self.pw.show()
        #self.pw.close()
    def on_import_click(self):
       #self.import_button.animateClick()
       button_clicked = True
       text  =  self.input_box.toPlainText()	
       self.process_and_launch(text)
       #str(type(input_box)))
    def load_file_click(self):
        from aqt.utils import getFile
        import io
        file_name  =  str(getFile(self.pw,  _("Import"),  None,  key = "import", filter = "*.txt"))
        if not file_name == "[]":
            try:
                with io.open(file_name, encoding = "utf-8-sig") as file:
                    self.process_and_launch(file.read()) 
            except IOError:
                print2("Error opening file "+file_name)
        
        #getFile
       
    def close_window(self):
        try:
            mw.reset()
        finally:
            #self.sw.close()
            self.pw.close()
    def process_and_launch(self, text):
        # Will be splitting on: ,  <\n>:
        timer.reset()
        timer("process_and_launch")
        limit = 20
        print(text)
        wlist = [q.lower() for word in re.split("[\n, .!?\"\(\):;\-]", text) for q in word.split()]
                                
                               
                   
        if  len(wlist)>limit:
            print2("Number of the words exceeds the allowed limit ("+str(len(wlist))+"/"+str(limit)+")")
        else:
            from_lang = self.from_box.currentText()
            include_translations = self.t_checkbox.isChecked()
            include_mp3 = self.audio_checkbox.isChecked()
            self.launch_import(wlist, from_lang, include_translations, include_mp3)
            # w.close()    
          
    def search_dic(self, dic):
        import urllib, re
        text  =  self.input_box.toPlainText()	
        
        wlist = [q for word in re.split("[\n, .!?\"\(\):;\-]", text) for q in  word.split()]
        qurl  =  QUrl()
        
        dicdict = {"Cambridge":"https://dictionary.cambridge.org/dictionary/english/", "Oxford": "https://www.lexico.com/en/definition/", "Bab.la": "https://cs.bab.la/slovnik/anglicky-cesky/", "M-W":"https://www.merriam-webster.com/dictionary/", "Collins":"https://www.collinsdictionary.com/dictionary/english/", "Lingea.cz":"https://slovniky.lingea.cz/anglicko-cesky/"}
        
        try:
            baseUrl = dicdict[dic]    
            for word in wlist:
                url  =  baseUrl + urllib.quote(word.encode("utf-8"))
                qurl.setEncodedUrl(url)
                QDesktopServices.openUrl(qurl)
        except KeyError:
            print2("Some of the dictionaries in "+os.path.join(os.path.dirname(__file__), 'VDsettings.txt')+" are undefined. Please correct or remove the fields 'self.lookup_dictionary' and/or 'cesky_slovnik' ")
    def settings_window(self):
        
        self.pw.settings  =  self.sw  =  QDialog(None, Qt.WindowMinMaxButtonsHint)#(None, Qt.WindowMinMaxButtonsHint | Qt.WindowContextHelpButtonHint)
        
        self.sw.setWindowTitle("Settings")
        geom = self.pw.frameGeometry()
        self.sw.setGeometry(geom.x()+geom.width()/4,  geom.y()+geom.height()/4,  geom.width()/2,  6*geom.height()/12)  
        vlayout = QVBoxLayout(self.sw)
        texts = ["Default language", "Show tooltips", "Add audio by default?", "Add translations by default?", "English/English dictionary", u"Anglicko-český slovník"]
        settings_list = [["British English", "American English"], ["Yes", "No"], ["Yes", "No"], ["Yes", "No"], [".", "."], ["a", "b", "c"]]
        box = dict()
        for text, settings in zip(texts, settings_list):
            tLab = QLabel(text)
            box[text]  =  QComboBox()
            
            for option in settings: 
                box[text].addItem(option)
            box[text].setCurrentIndex(0)
            hlayout = QHBoxLayout()
            hlayout.addWidget(tLab)
            hlayout.addWidget(box[text])
            vlayout.addLayout(hlayout)
        
        from_lang = self.from_box.currentText
        def tooltip_change():
            #print2("Bum")
            #print2(str(box["Show tooltips"].currentIndex))
            if box["Show tooltips"].currentIndex() == 0:
             #   print2("Bumbum")
                self.show_tooltips = True
                self.setup_tooltips()
            else:
                self.show_tooltips = False
                for item in self.widget_collection:
                    item.setToolTip("")
        
    
        self.combo_action(box["Show tooltips"], self.show_tooltips, tooltip_change)
        self.sw.exec_()
        
        #self.sw.show()
    def combo_action(self, cb, option_flag, action):
        if option_flag:
        
            cb.setCurrentIndex(0)
        else:    
        
            cb.setCurrentIndex(1)             
        cb.currentIndexChanged.connect(action)
        
    def setup_tooltips(self):
        self.input_helptext = "You can separate your words by spaces,  newlines or common interpunction marks.\nFor compounds,  phrasal verbs,  etc.,  use '_' instead of space.\nPress Ctrl+Enter or Ctrl+I to import. To see other shortcuts,  press AltGr."    
        self.input_box.setToolTip(self.input_helptext)
        self.input_label.setToolTip(self.input_helptext)    
        self.import_button.setToolTip("Creates new cards based on entries in Oxford Dictionaries (lexico.com). \nThis might take a while.")
        self.load_file_button.setToolTip("Loads your vocabulary list from a text file.\nImporting will then start immediately.")
        self.cambridge_button.setToolTip("Opens each entry on a seperate tab in your browser")
        self.lingea_button.setToolTip(u"Pro každé slovo vyhledá český překlad a otevře jej v prohlížeči")
        self.audio_checkbox.setToolTip("Adds mp3 files with pronunciations.\nSignificantly slows the whole process.")  
        self.t_checkbox.setToolTip(u"Přidá hesla z anglicko-českého svobodného slovníku GNU/FDL.\nProces bude trvat trochu déle.")
    
    def launch_import(self, wlist, from_lang, include_translations, include_mp3):
        
            
        lw = len(wlist)  
        
        timer("launch_import")
        if lw>0:
            try:

                aqt.mw.progress.start(label = "Downloading dictionary entries", max = lw)            
                aqt.mw.progress.update(value = 0)
                self.sw, erw = CreateImportList(wlist, from_lang, include_translations, include_mp3)
                aqt.mw.progress.update(value = 0, label = "Downloading audio...")
                timer("Stahovani dat")
                threads_download_mp3s()
            finally:
                aqt.mw.progress.finish()
                #print2("It took {0} seconds".format(time.time()-start))
                timer("Konec")
                timer.save_results()

        else:
            print2("No words to import")
            return
        
        sl = len(self.sw);el = len(erw);wl = len(wlist)
        if sl>0:
            import aqt.importing as imp
            from aqt import mw
            
            importerClass = None
            done = False
            file = "Import_list.txt"
            for i in imp.importing.Importers:
                if done:
                    break
                for mext in re.findall(r"[( ]?\*\.(.+?)[) ]",  i[0]):
                    if file.endswith("." + mext):
                        importerClass  =  i[1]
                        done  =  True
                        break
            if not importerClass:
                # if no matches,  assume TSV
                importerClass = imp.importing.Importers[0][1]
            importer = importerClass (mw.col, file)
            importer.model = mw.col.models.current()
            cd = mw.col.decks.current()["id"]
            mw.col.decks.select(cd)
            importer.allowHTML = True
            importer.delimiter = "@"
            try:
                importer.open()
                importer.run()
            
                if (sl == wl):
                    print2("Successfully imported all words!")  
                elif (sl<wl):
                    for i in range(len(self.sw)):
                        self.sw[i]=re.sub("_"," ",self.sw[i])
                        
                    sw_string=", ".join(self.sw)
                    erw_string = ""
                    for error_word in erw:
                        erw_string += ("\n'"+re.sub("_"," ",error_word[0])+"' ("+error_word[1]+")\n")
                    print2("Successfully imported "+str(sl)+"/"+str(wl)+" words: "+sw_string+".\n\n There has been a problem with the following words:\n"+erw_string)
            
            except Exception as err:
                print2("There has been an error while importing the downloaded data: "+err.read())
                raise err
            mw.reset()

        else:
            erw_string = ""
            for error_word in erw:                    
                erw_string += ("\n'"+error_word[0]+"' ("+error_word[1]+")\n")
            print2("Couldn't import any word. Either there has been an error of some sort or all the words are problematic:\n"+erw_string)  
def load_dict():
    global gnudict
    global trans_loaded
    try:
        trans_file = "gnudict.pickle"
        with io.open("../../addons21/VocabDownloader/"+trans_file, "rb") as dictfile:
            gnudict = pickle.load(dictfile)
            with open("Iamehere_pickle.txt", "w") as file:
                file.write("pickle_load")
    except IOError as err: 
        gnudict = None    
    finally:
        trans_loaded = True
            
def main():
    if not trans_loaded:
        
        x = threading.Thread(target = load_dict)
        x.start()
        
        
    IBox()
    #x.join()    
if __name__ == "__main__":
    import sys
    #
    main()
    

importAction  =  QAction("Vocabulary Importer Plugin",  mw)
importAction.triggered.connect(main)
mw.form.menuTools.addAction(importAction)
importAction.setShortcut("Ctrl+v")
