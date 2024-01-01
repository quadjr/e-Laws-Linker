#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import xml.etree.ElementTree as ET
import re
import csv
import itertools
import glob
import os

def jpnum_text(tag, title):
    return r"((第(?P<" + tag + r">[一二三四五六七八九十百千]+)" + title + r"([のノ](?P<" + tag + r"_sub>[一二三四五六七八九十百千]+))*)|((([前次](?P<" + tag + r"_rel>[一二三四五六七八九十百千]*))|同|(前?各))" + title + r"中?))"

# 3重括弧まで対応
brackets = "(（[^（）]*）)|(（[^（）]*（[^（）]*）[^（）]*）)|(（[^（）]*（[^（）]*（[^（）]*）[^（）]*）[^（）]*）)"
continue_words = f"(、|(及び)|(並びに)|(乃至)|(若しくは)|(又は)|(および)|(ならびに)|{brackets})"
law_pattern = re.compile(
    f"{continue_words}*"
    f"(?P<Link_text>"
    f"(?P<Law>(同((法)|(令)|(省令)|(規則)|(施行規則)))?(附則)?)"
    f"(次の)?(?P<Article>({jpnum_text('ArticleFrom', '条')}(から{jpnum_text('ArticleTo', '条')})?)?)(まで)?"
    f"(次の)?(?P<Paragraph>({jpnum_text('ParagraphFrom', '項')}(から{jpnum_text('ParagraphTo', '項')})?)?)(まで)?"
    f"(次の)?(?P<Item>({jpnum_text('ItemFrom', '号')}(から{jpnum_text('ItemTo', '号')})?)?)(まで)?"
    f")"
)
square_brackets_pattern = re.compile("「[^「」]*」")
title_brackets_pattern = re.compile(".*年.*第.*号（(?P<name>.*)）")
alias_pattern = re.compile(
    f"(?P<word>(([^、（）])|{brackets})*)（[^（）]*「(?P<alias>[^（）「」]*)」という"
)

def conv_jp_to_ad(num):
    digits = "〇一二三四五六七八九"
    digits_conv = {"":0, "〇":0, "一":1, "二":2, "三":3, "四":4, "五":5, "六":6, "七":7, "八":8, "九":9}

    match = re.fullmatch(
        "(?P<d0>[" + digits + "]?)"
        "(?P<ten>十?)(?P<d1>[" + digits + "]?)"
        "(?P<hundred>百?)(?P<d2>[" + digits + "]?)"
        "(?P<thousand>千?)(?P<d3>[" + digits + "]?)"
        "(?P<ten_thousand>万?)(?P<d4>[" + digits + "]?)"
        , num[::-1])

    d0 = match.group("d0")
    res = digits_conv[d0]

    d1 = match.group("d1")
    res += digits_conv[d1] * 10
    res += 10 if d1 == "" and match.group("ten") != "" else 0

    d2 = match.group("d2")
    res += digits_conv[d2] * 100
    res += 100 if d2 == "" and match.group("hundred") != "" else 0

    d3 = match.group("d3")
    res += digits_conv[d3] * 1000
    res += 1000 if d3 == "" and match.group("thousand") != "" else 0

    d4 = match.group("d4")
    res += digits_conv[d4] * 10000
    res += 10000 if d4 == "" and match.group("ten_thousand") != "" else 0

    return str(res)

def add_lookup_dict(lookup_dict, law_name, law_id):
    base_dict = lookup_dict
    for a in law_name:
        if a not in base_dict:
            base_dict[a] = {}
        base_dict = base_dict[a]
    if "" not in base_dict:
        base_dict[""] = []
    base_dict[""].append(law_id)

def lookup_dict(lookup_dict, sentence, offset = 0):
    law_ids = []
    law_name = ""
    base_dict = lookup_dict
    for i in itertools.count(offset):
        if "" in base_dict:
            law_ids = base_dict[""]
            law_name = sentence[offset:i]

        if i < len(sentence) and sentence[i] in base_dict:
            base_dict = base_dict[sentence[i]]
        else:
            break
    return law_name, law_ids

def get_relative_el(root, parent_map, el, tag, relative):
    parent = parent_map[el]
    self_el = None
    while True:
        if parent.tag == tag and parent in parent_map:
            self_el = parent
            parent = parent_map[parent]
            break
        
        if parent in parent_map:
            parent = parent_map[parent]
        else:
            # print("Failed to find tag. ", tag, el)
            raise IndexError

    elements = []
    self_index = -1
    for el in root.iter(tag):
        if el == self_el:
            self_index = len(elements)
        elements.append(el)
    
    if self_index < 0 or self_index + relative < 0 or self_index + relative >= len(elements):
        # print("Relative error", tag, self_index, relative, len(elements))
        raise IndexError

    return elements[self_index + relative].attrib["Num"]

def fix_law_name(law_name):
    law_name = law_name.replace("　抄", "")
    law_name_match = title_brackets_pattern.match(law_name)
    if law_name_match and law_name_match.group("name") != "刑法":
        law_name = law_name_match.group("name")
    return law_name

def is_unstable_elements(parent_map, el):
    is_unstable = False

    parent = parent_map[el]
    while parent is not None:
        if parent.tag == "SupplProvision" or parent.tag.startswith("Appdx") or parent.tag.startswith("Table"):
            is_unstable = True
            break

        if parent in parent_map:
            parent = parent_map[parent]
        else:
            break

    return is_unstable

def load_law_info():
    law_name_dict = {}
    law_info_dict = {}
    with open('all_xml/all_law_list.csv', encoding="utf_8_sig") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            if (len(row["未施行"]) > 0):
                continue

            law_name = fix_law_name(row["法令名"])

            add_lookup_dict(law_name_dict, law_name, row["法令ID"])
            add_lookup_dict(law_name_dict, row["法令番号"], row["法令ID"])
            law_info_dict[row["法令ID"]] = row

    with open('short_law_names.csv') as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            # 法令番号から法令IDを検索
            values = list(row.values())
            law_name, law_ids = lookup_dict(law_name_dict, values[1])
            if law_name != values[1] or len(law_ids) != 1:
                print('invalid law number : ', values[1], law_name, law_ids)
                continue

            # 法令名から法令IDを検索（整合確認用）
            law_name = fix_law_name(values[0])
            law_name_check, law_ids_check = lookup_dict(law_name_dict, law_name)
            if law_name_check != law_name or law_ids[0] not in law_ids_check:
                print('invalid law name : ', values[0], law_name_check, law_ids_check)
                continue

            for short_name in values[2:]:
                if len(short_name) > 0:
                    add_lookup_dict(law_name_dict, short_name, law_ids[0])

    return law_name_dict, law_info_dict


law_name_dict, law_info_dict = load_law_info()

xml_files = glob.glob("./all_xml/**/*.xml", recursive=True)
xml_files.sort()
for file_no, xml_file in enumerate(xml_files):
    print(file_no + 1, len(xml_files), xml_file)

    output_path = os.path.join("linked", xml_file)
    if os.path.isfile(output_path):
        continue

    tree = ET.parse(xml_file)
    root = tree.getroot()
    parent_map = {c: p for p in tree.iter() for c in p}
    alias_dict = {}

    self_law = xml_file.split("/")[-1].split("_")[0]

    pre_law = None
    pre_artcile = None
    pre_paragraph = None
    pre_item = None
    for sentence in root.iter('Sentence'):
        self_article = None
        self_paragraph = None
        self_item = None

        is_unstable = is_unstable_elements(parent_map, sentence)

        parent = parent_map[sentence]
        while parent is not None:
            if "Num" in parent.attrib:
                num = parent.attrib["Num"]
                if parent.tag == "Article":
                    self_article = num
                elif parent.tag == "Paragraph":
                    self_paragraph = num
                elif parent.tag == "Item":
                    self_item = num
            
            if parent in parent_map:
                parent = parent_map[parent]
            else:
                break

        text = sentence.text if sentence.text is not None else ''
        for child in sentence:
            # TODO Support Ruby
            # if child.tag == "Ruby" and child.text is not None:
            #     text += child.text
            if child.tail is not None:
                text += child.tail

        # リンクを検索
        offset = 0
        link_list = []
        link_end_dict = {}
        while offset < len(text):
            # 「」で括られた部分はスキップ
            brackets_match = square_brackets_pattern.match(text, offset)
            if brackets_match:
                offset += len(brackets_match.group())
                continue

            alias_match = alias_pattern.match(text, offset)

            # 法令名辞書からの検索
            law_name, law_ids = lookup_dict(law_name_dict, text, offset)
            if len(law_name) > 0: # 法令名辞書
                start_pos = offset
                offset += len(law_name)
                end_pos = offset

                end_check_pos = None

                # カッコ書きによる法令番号指定の対応確認
                if len(text) > offset and text[offset] == '（':
                    law_name_check, law_ids_check = lookup_dict(law_name_dict, text, offset + 1)
                    if len(law_name_check) > 0:
                        start_check_pos = offset + 1
                        end_check_pos = offset + len(law_name_check) + 1
                        law_ids = list(filter(lambda x: x in law_ids_check, law_ids))

                # 法令名不整合 または 法令不確定
                if len(law_ids) != 1:
                    print("法令名不整合 または 法令不確定", law_name, law_ids)
                    continue
                else:
                    # print(law_name, law_ids[0])
                    pre_law = law_ids[0]
                    pre_artcile = None
                    pre_paragraph = None
                    pre_item = None
                    if end_pos not in link_end_dict:
                        link_end_dict[end_pos] = law_ids[0]
                        link_list.append({"start":start_pos, "end":end_pos, "law": law_ids[0], "article":None, "paragraph":None, "item":None})
                    if end_check_pos is not None and end_check_pos not in link_end_dict:
                        link_end_dict[end_check_pos] = law_ids[0]
                        link_list.append({"start":start_check_pos, "end":end_check_pos, "law": law_ids[0], "article":None, "paragraph":None, "item":None})

                if alias_match and law_name == alias_match.group("word"):
                    alias = alias_match.group("alias")
                    add_lookup_dict(alias_dict, alias, law_ids[0])

                continue

            # エイリアス辞書からの検索
            law_name, law_ids = lookup_dict(alias_dict, text, offset)
            if len(law_name) > 0: # 法令名辞書
                start_pos = offset
                offset += len(law_name)
                end_pos = offset

                pre_law = law_ids[0]
                pre_artcile = None
                pre_paragraph = None
                pre_item = None
                if end_pos not in link_end_dict:
                    link_end_dict[end_pos] = law_ids[0]
                    link_list.append({"start":start_pos, "end":end_pos, "law": law_ids[0], "article":None, "paragraph":None, "item":None})

                continue

            try:
                # 同法/同施行規則、条、項、号指定
                law_match = law_pattern.match(text, offset)
                if (len(law_match.group("Law")) > 0 or
                    len(law_match.group("Article")) > 0 or
                    len(law_match.group("Paragraph")) > 0 or
                    len(law_match.group("Item")) > 0):
                    spefify_level = 0
                    is_relative = False

                    if len(law_match.group("Law")) > 0 and law_match.group("Law") != "附則":
                        law = pre_law
                        spefify_level = 1
                        pre_artcile = None
                    elif law_match.start() in link_end_dict:
                        law = link_end_dict[law_match.start()]
                        spefify_level = 1
                        pre_artcile = None
                        pre_paragraph = None
                    else:
                        law = self_law

                    if len(law_match.group("Article")) > 0:
                        spefify_level = 2
                        from_num = law_match.group("ArticleFrom")
                        if law_match.group("ArticleFrom_rel"):
                            rel_num = int(conv_jp_to_ad(law_match.group("ArticleFrom_rel")))
                        else:
                            rel_num = 1

                        if from_num is not None and len(from_num) > 0:
                            article = conv_jp_to_ad(from_num)
                            if law_match.group("ArticleFrom_sub") is not None:
                                article += "_" + conv_jp_to_ad(law_match.group("ArticleFrom_sub"))
                        elif "各条" in law_match.group("Article"):
                            article = "1"
                        elif "前" in law_match.group("Article"):
                            is_relative = True
                            article = get_relative_el(root, parent_map, sentence, "Article", -rel_num)
                        elif "次" in law_match.group("Article"):
                            is_relative = True
                            article = get_relative_el(root, parent_map, sentence, "Article",  rel_num)
                        else:
                            article = pre_artcile
                        pre_paragraph = None
                    else:
                        article = self_article

                    if len(law_match.group("Paragraph")) > 0:
                        spefify_level = 3
                        from_num = law_match.group("ParagraphFrom")
                        if law_match.group("ParagraphFrom_rel"):
                            rel_num = int(conv_jp_to_ad(law_match.group("ParagraphFrom_rel")))
                        else:
                            rel_num = 1

                        if from_num is not None and len(from_num) > 0:
                            paragraph = conv_jp_to_ad(from_num)
                            if law_match.group("ParagraphFrom_sub") is not None:
                                paragraph += "_" + conv_jp_to_ad(law_match.group("ParagraphFrom_sub"))
                        elif "各項" in law_match.group("Paragraph"):
                            paragraph = "1"
                        elif "前" in law_match.group("Paragraph"):
                            is_relative = True
                            paragraph = get_relative_el(root, parent_map, sentence, "Paragraph", -rel_num)
                        elif "次" in law_match.group("Paragraph"):
                            is_relative = True
                            paragraph = get_relative_el(root, parent_map, sentence, "Paragraph",  rel_num)
                        else:
                            paragraph = pre_paragraph
                    else:
                        paragraph = self_paragraph

                    if len(law_match.group("Item")) > 0:
                        if spefify_level == 2:
                            paragraph = "1"
                        spefify_level = 4
                        from_num = law_match.group("ItemFrom")                    
                        if law_match.group("ItemFrom_rel"):
                            rel_num = int(conv_jp_to_ad(law_match.group("ItemFrom_rel")))
                        else:
                            rel_num = 1

                        if from_num is not None and len(from_num) > 0:
                            item = conv_jp_to_ad(from_num)
                            if law_match.group("ItemFrom_sub") is not None:
                                item += "_" + conv_jp_to_ad(law_match.group("ItemFrom_sub"))
                        elif "各号" in law_match.group("Item"):
                            item = "1"
                        elif "前" in law_match.group("Item"):
                            is_relative = True
                            item = get_relative_el(root, parent_map, sentence, "Item", -rel_num)
                        elif "次" in law_match.group("Item"):
                            is_relative = True
                            item = get_relative_el(root, parent_map, sentence, "Item",  rel_num)
                    else:
                        item = None

                    if spefify_level < 2:
                        article = None
                    if spefify_level < 3:
                        paragraph = None

                    if not (is_unstable and is_relative):
                        link_end_dict[law_match.end("Link_text")] = law
                        link_list.append({"start":law_match.start("Link_text"), "end":law_match.end("Link_text"),
                            "law": law, "article":article, "paragraph":paragraph, "item":item})

                    pre_law = law
                    pre_artcile = article
                    pre_paragraph = paragraph
                    pre_item = item
                    offset += len(law_match.group())
                    continue
            except:
                if not is_unstable:
                    print("同法/同施行規則、条、項、号指定 例外", text[offset:min(len(text), offset + 100)])

            offset += 1

        link_list.sort(key=lambda x: x["start"])

        for link in link_list:
            start_pos = link["start"]
            end_pos = link["end"]
            law = link["law"]
            article = link["article"]
            paragraph = link["paragraph"]
            item = link["item"]
            if law is None:
                print("リンク先不明", link, sentence.text)
                continue

            text1 = sentence.text if sentence.text is not None else ''
            if start_pos < len(text1):
                if end_pos > len(text1):
                    raise LookupError

                sentence.text = text1[:start_pos]
                a_tag = ET.Element('A', law=law)
                a_tag.text = text1[start_pos:end_pos]
                a_tag.tail = text1[end_pos:]
                if article is not None: a_tag.attrib["article"] = article
                if paragraph is not None: a_tag.attrib["paragraph"] = paragraph
                if item is not None: a_tag.attrib["item"] = item
                sentence.insert(0, a_tag)
                continue

            offset = len(text1)
            for i, child in enumerate(sentence):
                text1 = child.tail if child.tail is not None else ''
                child_offset = 0
                if child.tag == 'A' and child.text is not None:
                    text1 = child.text + text1
                    child_offset = len(child.text)

                if start_pos - offset < len(text1):
                    if end_pos - offset > len(text1) or start_pos - offset < child_offset:
                        print(text)
                        print(i, start_pos, offset, child_offset, text1)
                        raise LookupError

                    child.tail = text1[child_offset:start_pos - offset]
                    a_tag = ET.Element('A', law=law)
                    a_tag.text = text1[start_pos - offset:end_pos - offset]
                    a_tag.tail = text1[end_pos - offset:]
                    if article is not None: a_tag.attrib["article"] = article
                    if paragraph is not None: a_tag.attrib["paragraph"] = paragraph
                    if item is not None: a_tag.attrib["item"] = item
                    sentence.insert(i + 1, a_tag)
                    break

                offset += len(text1)
            else:
                raise LookupError

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    print("Wrote", output_path)
    tree.write(output_path, encoding='utf-8', xml_declaration=True)
