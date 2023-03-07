import pickle
import sys
import os
from tqdm import tqdm
from pathlib import Path
from copy import copy
from bs4 import BeautifulSoup as bs
from ebooklib import epub, ITEM_DOCUMENT
from functools import partial
import multiprocessing
import threading

IS_TEST = False

class BEPUB:
    def __init__(self, epub_name, model, key, resume, language, model_api_base=None, options=None):
        self.epub_name = epub_name
        self.new_epub = epub.EpubBook()
        self.translate_model = model(key, language, model_api_base, options)
        self.origin_book = epub.read_epub(self.epub_name)
        self.p_to_save = []
        self.resume = resume
        self.bin_path = f"{Path(epub_name).parent}/.{Path(epub_name).stem}.temp.bin"
        if self.resume:
            self.load_state()

    @staticmethod
    def _is_special_text(text):
        return text.isdigit() or text.isspace()

    def _make_new_book(self, book):
        new_book = epub.EpubBook()
        new_book.metadata = book.metadata
        new_book.spine = book.spine
        new_book.toc = book.toc
        return new_book
    
    def _make_html_markup_qa(self, new_p):
        
        list_q_a = new_p.text.split('\n')
        list_q_a = list(filter(lambda x: len(x) > 0, list_q_a))
        new_p = ""
        for i in range(len(list_q_a)//2):
            new_p += f"""<details class="details-example">\
                            <summary>{list_q_a[i*2]}</summary>\
                            <ul>\
                                <li>{list_q_a[(i*2)+1]}</li>\
                            </ul>\
                        </details>\n"""
        new_p = bs(new_p)
        return new_p
    
    def run_model(self, p, pbar, is_test_done, TEST_NUM, p_to_save_len, index):
        
        if is_test_done or not p.text or self._is_special_text(p.text):
            return
        new_p = copy(p)
        # TODO banch of p to translate then combine
        # PR welcome here
        if self.resume and index < p_to_save_len:
            new_p.string = self.p_to_save[index]
        else:
            new_p.string = self.translate_model.translate(p.text)
            self.p_to_save.append(new_p.text)
        
        new_p = self._make_html_markup_qa(new_p)
        p.insert_after(new_p)
        index += 1
        if index % 50 == 0:
            self._save_progress()
        # pbar.update(delta) not pbar.update(index)?
        pbar.update(1)
        if IS_TEST and index > TEST_NUM:
            return

    def make_bilingual_book(self, options):
        IS_TEST = options.test
        TEST_NUM = options.test_num
        new_book = self._make_new_book(self.origin_book)
        all_items = list(self.origin_book.get_items())
        all_p_length = sum(
            len(bs(i.content, "html.parser").findAll("p"))
            if i.file_name.endswith(".xhtml")
            else len(bs(i.content, "xml").findAll("p"))
            for i in all_items
        )
        pbar = tqdm(total=TEST_NUM) if IS_TEST else tqdm(total=all_p_length)
        index = 0
        p_to_save_len = len(self.p_to_save)
        try:
            for item in self.origin_book.get_items():
                if item.get_type() == ITEM_DOCUMENT:
                    soup = bs(item.content, "html.parser")
                    p_list = soup.findAll("p")
                    is_test_done = IS_TEST and index > TEST_NUM

                    thread_list = []
                    for p in p_list:
                        thread_temp = threading.Thread(target=self.run_model, args=(p,pbar, is_test_done, TEST_NUM, p_to_save_len,index,))
                        thread_temp.start()
                        thread_list.append(thread_temp)

                    for thread_pp in thread_list:
                        thread_pp.join()
                    item.content = soup.prettify().encode()

                new_book.add_item(item)
            name, _ = os.path.splitext(self.epub_name)
            epub.write_epub(f"{name}_bilingual.epub", new_book, {})
            pbar.close()
        except (KeyboardInterrupt, Exception) as e:
            print(e)
            print("you can resume it next time")
            self._save_progress()
            self._save_temp_book()
            sys.exit(0)

    def load_state(self):
        try:
            with open(self.bin_path, "rb") as f:
                self.p_to_save = pickle.load(f)
        except:
            raise Exception("can not load resume file")

    def _save_temp_book(self):
        origin_book_temp = epub.read_epub(
            self.epub_name
        )  # we need a new instance for temp save
        new_temp_book = self._make_new_book(origin_book_temp)
        p_to_save_len = len(self.p_to_save)
        index = 0
        # items clear
        try:
            for item in self.origin_book.get_items():
                if item.get_type() == ITEM_DOCUMENT:
                    soup = (
                        bs(item.content, "xml")
                        if item.file_name.endswith(".xhtml")
                        else bs(item.content, "html.parser")
                    )
                    p_list = soup.findAll("p")
                    for p in p_list:
                        if not p.text or self._is_special_text(p.text):
                            continue
                        # TODO banch of p to translate then combine
                        # PR welcome here
                        if index < p_to_save_len:
                            new_p = copy(p)
                            new_p.string = self.p_to_save[index]
                            print(new_p.string)
                            p.insert_after(new_p)
                            index += 1
                        else:
                            break
                    # for save temp book
                    item.content = soup.prettify().encode()
                new_temp_book.add_item(item)
            name, _ = os.path.splitext(self.epub_name)
            epub.write_epub(f"{name}_bilingual_temp.epub", new_temp_book, {})
        except Exception as e:
            # TODO handle it
            print(e)

    def _save_progress(self):
        try:
            with open(self.bin_path, "wb") as f:
                pickle.dump(self.p_to_save, f)
        except:
            raise Exception("can not save resume file")
