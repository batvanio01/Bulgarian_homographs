import csv
import itertools
import os


class BulgarianStressPredictor:

    def __init__(self, csv_path="words_database.csv"):
        self.database = {}
        self.csv_path = csv_path

        # Списък с "леки" думи, които в потока на речта НЯМАТ собствено силно ударение
        self.clitics = {
            "на",
            "за",
            "от",
            "по",
            "с",
            "със",
            "в",
            "във",
            "и",
            "а",
            "но",
            "че",
            "ли",
            "ще",
            "да",
            "не",
            "се",
            "си",
            "ми",
            "ти",
            "му",
            "и",
            "го",
            "я",
            "ни",
            "ви",
            "им",
            "той",
            "тя",
            "то",
            "те",
        }

        self.load_database()

    def load_database(self):
        """Зарежда 933 000 думи бързо в паметта"""
        if not os.path.exists(self.csv_path):
            print(f"Грешка: Базата данни '{self.csv_path}' не е намерена!")
            return

        print("Зареждане на езиковата база данни в паметта...")
        with open(self.csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="|")
            next(reader)  # Пропускаме заглавния ред

            for row in reader:
                if not row or len(row) < 3:
                    continue
                word = row[0].lower()

                variants = []
                # Форма 1
                if row[1] and row[2]:
                    v_nums = [float(x) for x in row[2].split(",")]
                    # Бележим, че това е Форма 1 (основната езикова форма)
                    variants.append({"text": row[1], "vector": v_nums, "is_first_form": True})
                # Форма 2
                if row[3] and row[4]:
                    v_nums = [float(x) for x in row[4].split(",")]
                    variants.append({"text": row[3], "vector": v_nums, "is_first_form": False})
                # Форма 3
                if row[5] and row[6]:
                    v_nums = [float(x) for x in row[6].split(",")]
                    variants.append({"text": row[5], "vector": v_nums})

                if variants:
                    self.database[word] = variants
        print(f"Успешно заредени {len(self.database)} уникални думи!")

    def calculate_rhythm_score(self, combo, full_vector):
        score = 0
        
        # 1. АНАЛИЗ НА ЧЕСТОТНИЯ РИТЪМ (Остава непроменен)
        peak_positions = [i for i, val in enumerate(full_vector) if val >= 700]
        if len(peak_positions) >= 2:
            distances = [peak_positions[i] - peak_positions[i-1] for i in range(1, len(peak_positions))]

            for dist in distances:
                if dist <= 1:
                    score -= 50  # Наказание САМО за неестествен сблъсък (сричка до сричка)
                elif dist == 2:
                    score += 10  # Напълно нормално разстояние за българския език!
                elif 3 <= dist <= 6:
                    score += 20  # Идеален, плавен ритъм
                else:
                    score -= 2   # Минимално наказание за твърде монотонна пауза

        # --- ЖОКЕР ЗА СТАТИСТИЧЕСКА ЧЕСТОТА (Защита за "само" и "били") ---
        # Тъй като Форма 1 в базата данни почти винаги е най-използваната в езика,
        # даваме лек, но стабилен бонус (+15 точки), ако алгоритъмът избере Форма 1.
        # Така, ако ритъмът е сравнително еднакъв, компютърът ще избере "сАмо" пред "самО".
        for word_info in combo:
            # Проверяваме дали в името на текста има маркер или дали е първи избор
            # Ако моделът се колебае, този бонус ще наклони везните към нормалния език
            if 'is_first_form' in word_info and word_info['is_first_form']:
                score += 15
                    
        # 2. ПОПРАВЕНОТО ЗЛАТНО ПРАВИЛО ЗА ОМОГРАФИТЕ
        used_base_words = {}
        for word_info in combo:
            text_version = word_info['text']
            
            # ИЗЧИСТВАМЕ НАПЪЛНО УДАРЕНИЯТА (Премахваме главните букви за сравнение на корена)
            # Така "вЪлна" и "вълнА" ще станат еднаквата базова дума "вълна"
            base_word = "".join([c.lower() for c in text_version])
            
            # Пропускаме препинателните знаци и съвсем кратките думи
            if base_word in [",", ".", "!", "?", "и", "на", "за", "от", "в", "с"]:
                continue
                
            if base_word in used_base_words:
                previous_form = used_base_words[base_word]
                if previous_form != text_version:
                    # УРА! Намерихме истински различни форми на една и съща дума -> СЕРИОЗЕН БОНУС!
                    score += 120  
                else:
                    # Избрали сме еднаква форма за омографа в едно изречение -> Тежко наказание!
                    score -= 80  
            else:
                used_base_words[base_word] = text_version
                
        return score

    def process_sentence(self, sentence):
        """ 
        Разделя изречението на отделни фрази по запетаи/пунктуация.
        Изчислява ритъма за всяка фраза ИЗОЛИРАНО, за да няма математически шум.
        """
        import re
        
        # Регулярен израз, който цепи по препинателни знаци, но ги пази като разделители
        # Резултатът ще е списък от фрази и пунктуация: ['Силната водна пара...', ',', ' а аз нямах...', '.']
        tokens = re.split(r'([,\.\!?;\])', sentence)
        
        processed_parts = []
        
        for token in tokens:
            if not token:
                continue
                
            # Ако токенът е просто пунктуация, пазим го директно
            if token in [",", ".", "!", "?", ";"]:
                processed_parts.append(token)
                continue
                
            # Почистваме празни пространства около фразата
            phrase = token.strip()
            if not phrase:
                continue
                
            # Обработваме текущата фраза самостоятелно
            words = phrase.split()
            phrase_options = []
            is_any_omograph = False
            
            for idx, word in enumerate(words):
                word_lower = word.lower()
                
                if word_lower in self.database:
                    variants = self.database[word_lower]
                    
                    # ПРАВИЛО ЗА ИМЕТО "ЕДНА" (Пази се от предната версия)
                    # Тъй като сме вътре във фраза, проверяваме дали е с главна буква
                    if word_lower == "една" and word[0].isupper():
                        # Ако е в началото на цялото изречение (първа дума), математиката ще реши.
                        # Но ако пред нея във фразата има друга дума, гарантирано е име.
                        if idx > 0:
                            name_variants = [v for v in variants if any(c.isupper() for c in v['text'])]
                            if name_variants:
                                phrase_options.append(name_variants)
                                continue
                    
                    # КОРЕКЦИЯ ЗА ЛЕКИТЕ ДУМИ (Буфер 450Hz)
                    if word_lower in self.clitics or word_lower == "една":
                        clitic_variants = []
                        for v in variants:
                            clean_vector = [450.0 if x == 750.0 else x for x in v['vector']]
                            clitic_variants.append({'text': v['text'].lower(), 'vector': clean_vector})
                        phrase_options.append(clitic_variants)
                    else:
                        phrase_options.append(variants)
                        if len(variants) > 1:
                            is_any_omograph = True
                else:
                    # Защита за непознати думи (сричково броене, за да пази разстоянието)
                    vowels = "аоеиуъяюАОЕИУЪЯЮ"
                    syllable_count = sum(1 for char in word if char in vowels)
                    if syllable_count == 0: syllable_count = 1
                    fake_vector = [350.0] * syllable_count
                    phrase_options.append([{"text": word, "vector": fake_vector}])
            
            # Ако във фразата няма омографи, взимаме първия вариант
            if not is_any_omograph:
                best_phrase_text = " ".join([opt[0]['text'] for opt in phrase_options])
                processed_parts.append(best_phrase_text)
                continue
                
            # Генерираме комбинации САМО за тази фраза
            all_combinations = list(itertools.product(*phrase_options))
            best_score = -99999
            best_phrase_text = phrase
            
            for combo in all_combinations:
                full_vector = []
                text_parts = []
                
                for word_info in combo:
                    full_vector.extend(word_info["vector"])
                    full_vector.append(0) # Интервал
                    text_parts.append(word_info["text"])
                    
                current_score = self.calculate_rhythm_score(combo, full_vector)
                
                if current_score > best_score:
                    best_score = current_score
                    best_phrase_text = " ".join(text_parts)
                    
            processed_parts.append(best_phrase_text)
            
        # Сглобяваме изречението обратно, като коригираме интервалите пред знаците
        final_sentence = ""
        for part in processed_parts:
            if part in [",", ".", "!", "?", ";", "-"]:
                final_sentence = final_sentence.rstrip() + part + " "
            else:
                final_sentence += part + " "
                
        return final_sentence.strip()

    def process_sentence(self, sentence):
        """ Приема изречение, пази запетаите като физически паузи и намира точния ритъм. """
        # Отделяме препинателните знаци с интервал, за да ги хванем като отделни елементи
        raw_tokens = sentence.replace(".", " .").replace(",", " ,").replace("!", " !").replace("?", " ?").split()
        
        sentence_options = []
        is_any_omograph = False
        
        for token in raw_tokens:
            token_lower = token.lower()
            
            # АКО Е ЗАПЕТАЯ ИЛИ ДРУГ ЗНАК - ТОВА Е ПАУЗА (ВЪЗДУХ)
            if token in [",", ".", "!", "?"]:
                sentence_options.append([{"text": token, "vector": [0.0, 0.0, 0.0, 0.0]}])
            
            elif token_lower in self.database:
                variants = self.database[token_lower]
                
                # Корекция за малките думи (буфер от 450Hz)
                if token_lower in self.clitics:
                    clitic_variants = []
                    for v in variants:
                        clean_vector = [450.0 if x == 750.0 else x for x in v['vector']]
                        clitic_variants.append({'text': v['text'].lower(), 'vector': clean_vector})
                    sentence_options.append(clitic_variants)
                else:
                    sentence_options.append(variants)
                    if len(variants) > 1:
                        is_any_omograph = True
            else:
                sentence_options.append([{'text': token, 'vector': [0, 0, 0]}])
                
        if not is_any_omograph:
            final_sentence = " ".join([opt[0]['text'] for opt in sentence_options])
            return final_sentence.replace(" ,", ",").replace(" .", ".").replace(" !", "!").replace(" ?", "?")
            
        all_combinations = list(itertools.product(*sentence_options))
        best_score = -99999
        best_text_version = sentence
        
        for combo in all_combinations:
            full_vector = []
            text_parts = []
            
            for word_info in combo:
                full_vector.extend(word_info['vector'])
                full_vector.append(0)  # Интервал между думите
                text_parts.append(word_info['text'])
                
            current_score = self.calculate_rhythm_score(combo, full_vector)
            
            if current_score > best_score:
                best_score = current_score
                best_text_version = " ".join(text_parts)
                
        # Почистваме интервалите пред запетаите на изхода
        best_text_version = best_text_version.replace(" ,", ",").replace(" .", ".").replace(" !", "!").replace(" ?", "?")
        return best_text_version
# -------------------------------------------------------------
if __name__ == "__main__":
    predictor = BulgarianStressPredictor()

    test_sentences = [
        # --- КАТЕГОРИЯ 1: Класически омографи (Контекст и баланс) ---
        "Силната водна пара бързо се издигаше, а аз нямах нито една пара.",
        "Морската вълна събори оградата, а баба ми спеше върху топлата овча вълна.",
        "Енергията се разпространява като бърза вълна от центъра на това тяло.",
        "Той мина бързо покрай старата изоставена мина и видя една птица.",
        
        # --- КАТЕГОРИЯ 2: Капанът "дали / дали" (Глагол срещу Съюз) ---
        "Щом вече са дали толкова пари, дали ще се върнат обратно?",
        "Дали ще дойде навреме, или пак ще каже, че са дали грешен адрес?",
        "Те не бяха дали никакви обещания, но дали това имаше значение сега?",
        
        # --- КАТЕГОРИЯ 3: Името "Една" срещу числителното "една" ---
        "Филмът го направи известната Една Колинс още миналата година.",
        "Видях само една птица на клона, а Една твърдеше, че са били две.",
        "Една нова идея промени всичко, докато Една Колинс снимаше своя филм.",
        
        # --- КАТЕГОРИЯ 4: Проверка за Запетаи и Физически Паузи ---
        "Ако искаш пари, пари ще получиш, но внимавай, защото това слънце пари.",
        "Когато вълната дойде, вълната на недоволството заля целия град.",
        "Щом мина през моста, той видя, че тази мина е опасна за хората.",
        
        # --- КАТЕГОРИЯ 5: Струпване на леки думи (Clitics) и дълги фрази ---
        "Той ли ще ми каже на мен за нея, след като не я е виждал от година?",
        "Дали ще даде да се разбере, че не иска да го вижда повече в тази къща?",
        "Нямам нито една идея за това как да се справя със силната водна пара.",
        
        # --- КАТЕГОРИЯ 6: Трудни преходи (Гласна до Гласна) ---
        "Тя изми своята дълга коса със старата и ръждясала желязна коса.",
        "Овчата вълна е топла, а морската вълна е студена и опасна за плуване.",
        "Били ли са го, че спи на работа.",
        "Били ли са там и са били горкият човек.",
        "Това кино го направи известната Една, която имаше само една мечта."
    ]

    print("\n--- РЕЗУЛТАТИ СЛЕД КОРЕКЦИИТЕ ---")

    for txt in test_sentences:
        res = predictor.process_sentence(txt)
        print(f"Вход:  {txt}")
        print(f"Изход: {res}")
        print("-" * 40)