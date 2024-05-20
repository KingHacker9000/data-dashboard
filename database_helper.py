import psycopg2, os
from psycopg2.extras import RealDictCursor
import base64

class Database:


    def __init__(self, dbname='test', user='postgres', password=os.environ['DB_password'], host='localhost', port='5432') -> None:
        try:
            self.connection = psycopg2.connect(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port
            )
        
        except (Exception, psycopg2.Error) as error:
            print(error)


    def get_user_id(self, google_id: str) -> int:
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            q = "SELECT * FROM users WHERE google_id = %s"
            cursor.execute(q, (google_id,))

            a = cursor.fetchone()
            cursor.close()
            if a is not None:
                user_id = a['user_id']
                return user_id
            return None

        except (Exception, psycopg2.Error) as error:
            print(error)
            return None
        
    def sign_up_user(self, google_id, picture_uri, email, name) -> bool:

        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            q = "INSERT INTO users (google_id, name, email, google_photo_uri) VALUES (%s, %s, %s, %s);"
            cursor.execute(q, (google_id, name, email, picture_uri))
            self.connection.commit()
            return True

        except (Exception, psycopg2.Error) as error:
            print(error)
            return False

    def close(self) -> None:
        self.connection.close()


    def get_form_name(self, form_id) -> str:

        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            q = "SELECT * FROM forms WHERE form_id=%s"
            cursor.execute(q, (form_id))
            return cursor.fetchone()['form_name']

        except (Exception, psycopg2.Error) as error:
            print(error)
            return 'Forms'
        

    def has_access(self, form_id: int, user_id: int) -> bool:
        cursor = self.connection.cursor(cursor_factory=RealDictCursor)

        select_query = "SELECT * FROM user_role WHERE user_role_id=(SELECT user_role_id FROM forms_access WHERE user_id = %s AND form_id = %s)"
        cursor.execute(select_query, (user_id, form_id))

        role = cursor.fetchone()

        if role is None or role['role_name'] not in ['CREATOR', 'VIEWER', 'SOLVER']:
            return False
        return True


    def has_read_access(self, form_id: int, user_id: int) -> bool:
        cursor = self.connection.cursor(cursor_factory=RealDictCursor)

        select_query = "SELECT * FROM user_role WHERE user_role_id=(SELECT user_role_id FROM forms_access WHERE user_id = %s AND form_id = %s)"
        cursor.execute(select_query, (user_id, form_id))

        role = cursor.fetchone()

        if role is None or role['role_name'] not in ['CREATOR', 'VIEWER']:
            return False
        return True


    def get_questions(self, form_id: int, user_id: int) -> list[dict] | bool:
        try:

            cursor = self.connection.cursor(cursor_factory=RealDictCursor)

            if not self.has_access(form_id, user_id):
                return False

            select_query = "SELECT * FROM questions LEFT JOIN question_types ON question_types.question_type_id = questions.question_type_id WHERE form_id=%s ORDER BY questions.position"
            cursor.execute(select_query, (form_id,))

            qns = cursor.fetchall()
            questions = []

            for q in qns:
                question = {
                    'text': q['question_text'],
                    'question_id': q['question_id'],
                    'type': q['question_type']
                }

                if q['question_type'] == 'dropdown':
                    select_query = 'SELECT * FROM dropdown_question_options WHERE question_id=%s ORDER BY position;' 
                    cursor.execute(select_query, (q['question_id'],))
                    question['options'] = [{"option_text": row['dropdown_question_option'], "option_id": row['dropdown_question_option_id']} for row in cursor.fetchall()]

                questions.append(question)

            cursor.close()

            return questions

        except (Exception, psycopg2.Error) as error:
            print(error)
            return False
        

    def get_question(self, question_id):

        cursor = self.connection.cursor(cursor_factory=RealDictCursor)

        select_query = "SELECT * FROM questions LEFT JOIN question_types ON question_types.question_type_id = questions.question_type_id WHERE question_id=%s ORDER BY questions.position"
        cursor.execute(select_query, (question_id,))

        q = cursor.fetchone()

        question = {
                    'text': q['question_text'],
                    'question_id': q['question_id'],
                    'type': q['question_type'],
                    'form_id': q['form_id']
        }

        cursor.close()

        return question


    def submit_form(self, form_id: int, user_id: int, answers:dict, files:dict) -> bool:
        try:

            cursor = self.connection.cursor(cursor_factory=RealDictCursor)

            if not self.has_access(form_id, user_id):
                return False
            
            insert_query = "INSERT INTO form_submissions (form_id, user_id) VALUES (%s, %s)"
            cursor.execute(insert_query, (form_id, user_id))
            self.connection.commit()

            select_query = "SELECT * FROM form_submissions WHERE form_id=%s AND user_id=%s ORDER BY form_submission_id DESC LIMIT 1"
            cursor.execute(select_query, (form_id, user_id))
            form_sub_id = int(cursor.fetchone()['form_submission_id'])
            
            for question_id in answers:
                q = self.get_question(question_id)
                q['answer'] = answers[question_id] if q['type'] != 'image' else files[q['question_id']].read()

                print(q)

                if q['form_id'] != form_id:
                    print('Wrong Form Submission!')
                    return False
                
                insert_query = "INSERT INTO form_answers (question_id, form_submission_id) VALUES (%s, %s)"
                cursor.execute(insert_query, (question_id, form_sub_id))
                self.connection.commit()

                select_query = "SELECT * FROM form_answers WHERE question_id=%s AND form_submission_id=%s ORDER BY form_answer_id DESC LIMIT 1"
                cursor.execute(select_query, (question_id, form_sub_id))
                form_ans_id = int(cursor.fetchone()['form_answer_id'])

                if q['type'] == 'text':

                    insert_query = "INSERT INTO text_answers (answer_id, answer) VALUES (%s, %s)"
                    cursor.execute(insert_query, (form_ans_id, q['answer']))
                    self.connection.commit()

                elif q['type'] == 'numeric':

                    insert_query = "INSERT INTO numeric_answers (answer_id, answer) VALUES (%s, %s)"
                    if q['answer'].isnumeric():
                        cursor.execute(insert_query, (form_ans_id, float(q['answer'])))
                        self.connection.commit()

                elif q['type'] == 'date':

                    insert_query = "INSERT INTO date_answers (answer_id, answer) VALUES (%s, %s)"
                    cursor.execute(insert_query, (form_ans_id, q['answer']))
                    self.connection.commit()

                elif q['type'] == 'coordinates':

                    insert_query = "INSERT INTO text_answers (answer_id, answer) VALUES (%s, %s)"
                    cursor.execute(insert_query, (form_ans_id, q['answer']))
                    self.connection.commit()

                elif q['type'] == 'dropdown':

                    insert_query = "INSERT INTO dropdown_answers (answer_id, dropdown_question_option_id) VALUES (%s, %s)"
                    cursor.execute(insert_query, (form_ans_id, q['answer']))
                    self.connection.commit()

                elif q['type'] == 'image':

                    print('Image found')

                    insert_query = "INSERT INTO image_answers (answer_id, answer) VALUES (%s, %s)"
                    cursor.execute(insert_query, (form_ans_id, q['answer']))
                    self.connection.commit()

            for question_id in files:
                q = self.get_question(question_id)
                q['answer'] = files[question_id].read()

                #print(q)

                if q['form_id'] != form_id:
                    print('Wrong Form Submission!')
                    return False
                
                insert_query = "INSERT INTO form_answers (question_id, form_submission_id) VALUES (%s, %s)"
                cursor.execute(insert_query, (question_id, form_sub_id))
                self.connection.commit()

                select_query = "SELECT * FROM form_answers WHERE question_id=%s AND form_submission_id=%s ORDER BY form_answer_id DESC LIMIT 1"
                cursor.execute(select_query, (question_id, form_sub_id))
                form_ans_id = int(cursor.fetchone()['form_answer_id'])

                if q['type'] == 'image':

                    print('Image found')

                    insert_query = "INSERT INTO image_answers (answer_id, answer) VALUES (%s, %s)"
                    cursor.execute(insert_query, (form_ans_id, q['answer']))
                    self.connection.commit()

            print('done')
            cursor.close()
            return True


        except (Exception, psycopg2.Error) as error:
            print(error)
            return False


    def get_all_responses(self, form_id: int, user_id: int):

        try:

            cursor = self.connection.cursor(cursor_factory=RealDictCursor)

            if not self.has_read_access(form_id, user_id):
                return False
            
            select_query = "SELECT * FROM questions WHERE form_id=%s ORDER BY position"
            cursor.execute(select_query, (form_id,))
            questions = cursor.fetchall()
            form_questions = [q['question_text'] for q in questions]
            questions = [self.get_question(question['question_id']) for question in questions]

            select_query = "SELECT * FROM form_submissions WHERE form_id=%s ORDER BY submitted_at DESC"
            cursor.execute(select_query, (form_id,))
            submissions = cursor.fetchall()


            form_responses = []

            for sub in submissions:
                answers = []
                for question in questions:
                    
                    select_query = 'SELECT * FROM form_answers WHERE question_id=%s AND form_submission_id=%s'
                    cursor.execute(select_query, (question['question_id'], sub['form_submission_id']))
                    a = cursor.fetchone()

                    if a is None:
                        answers.append('')
                        continue

                    a_id = a['form_answer_id']

                    if question['type'] == 'text':
                        select_query = "SELECT * FROM text_answers WHERE answer_id=%s"
                        cursor.execute(select_query, (a_id,))
                        val = {
                            'type': 'text',
                            'value': cursor.fetchone()['answer'] or ''
                        }
                        answers.append(val)

                    elif question['type'] == 'numeric':
                        select_query = "SELECT * FROM numeric_answers WHERE answer_id=%s"
                        cursor.execute(select_query, (a_id,))
                        ans = cursor.fetchone()

                        val = {
                            'type': 'text',
                            'value': ans['answer'] if ans is not None else ''
                        }

                        answers.append(val)

                    elif question['type'] == 'date':
                        select_query = "SELECT * FROM date_answers WHERE answer_id=%s"
                        cursor.execute(select_query, (a_id,))
                        ans = cursor.fetchone()

                        val = {
                            'type': 'text',
                            'value': ans['answer'] if ans is not None else ''
                        }
                        
                        answers.append(val)
                    
                    elif question['type'] == 'coordinates':
                        select_query = "SELECT * FROM text_answers WHERE answer_id=%s"
                        cursor.execute(select_query, (a_id,))
                        ans = cursor.fetchone()

                        val = {
                            'type': 'text',
                            'value': ans['answer'] if ans is not None else ''
                        }

                        answers.append(val)

                    elif question['type'] == 'dropdown':
                        select_query = "SELECT * FROM dropdown_answers WHERE answer_id=%s"
                        cursor.execute(select_query, (a_id,))
                        ddq_id = cursor.fetchone()['dropdown_question_option_id']

                        select_query = "SELECT * FROM dropdown_question_options WHERE dropdown_question_option_id=%s"
                        cursor.execute(select_query, (ddq_id,))

                        val = {
                            'type': 'text',
                            'value': cursor.fetchone()['dropdown_question_option'] or ''
                        }

                        answers.append(val)

                    elif question['type'] == 'image':
                        select_query = "SELECT * FROM image_answers WHERE answer_id=%s"
                        cursor.execute(select_query, (a_id,))
                        ans = cursor.fetchone()

                        if ans is None:
                            answers.append({'type': 'none'})
                            continue
                        img = base64.b64encode(ans['answer'])

                        val = {
                            'type': 'image',
                            'value': img.decode('utf-8'),
                            'answer_id': a_id
                        }
                        answers.append(val)

                form_responses.append({
                    'answers': answers,
                    'submission_id': sub['form_submission_id']
                })

            print('done')
            cursor.close()
            return form_questions, form_responses


        except (psycopg2.Error) as error:
            print(error)
            return False


    def get_response(self, form_id, user_id, submission_id):
        try:

            cursor = self.connection.cursor(cursor_factory=RealDictCursor)

            if not self.has_read_access(form_id, user_id):
                return False
            
            select_query = "SELECT * FROM questions WHERE form_id=%s ORDER BY position"
            cursor.execute(select_query, (form_id,))
            questions = cursor.fetchall()
            form_questions = [q['question_text'] for q in questions]

            questions = [self.get_question(question['question_id']) for question in questions]

            select_query = "SELECT * FROM form_submissions WHERE form_submission_id=%s"
            cursor.execute(select_query, (submission_id,))
            sub = cursor.fetchone()

            select_query = "SELECT * FROM users where user_id=%s"
            cursor.execute(select_query, (user_id,))
            user = cursor.fetchone()
            submission_details = {
                'user': user['name'],
                'email': user['email'],
                'submission time': sub['submitted_at']
            }

            answers = []
            for question in questions:
                
                select_query = 'SELECT * FROM form_answers WHERE question_id=%s AND form_submission_id=%s'
                cursor.execute(select_query, (question['question_id'], sub['form_submission_id']))
                a = cursor.fetchone()

                if a is None:
                    answers.append('')
                    continue

                a_id = a['form_answer_id']

                if question['type'] == 'text':
                    select_query = "SELECT * FROM text_answers WHERE answer_id=%s"
                    cursor.execute(select_query, (a_id,))
                    val = {
                        'type': 'text',
                        'value': cursor.fetchone()['answer'] or ''
                    }
                    answers.append(val)

                elif question['type'] == 'numeric':
                    select_query = "SELECT * FROM numeric_answers WHERE answer_id=%s"
                    cursor.execute(select_query, (a_id,))
                    ans = cursor.fetchone()

                    val = {
                        'type': 'text',
                        'value': ans['answer'] if ans is not None else ''
                    }

                    answers.append(val)

                elif question['type'] == 'date':
                    select_query = "SELECT * FROM date_answers WHERE answer_id=%s"
                    cursor.execute(select_query, (a_id,))
                    ans = cursor.fetchone()

                    val = {
                        'type': 'text',
                        'value': ans['answer'] if ans is not None else ''
                    }
                    
                    answers.append(val)
                
                elif question['type'] == 'coordinates':
                    select_query = "SELECT * FROM text_answers WHERE answer_id=%s"
                    cursor.execute(select_query, (a_id,))
                    ans = cursor.fetchone()

                    val = {
                        'type': 'text',
                        'value': ans['answer'] if ans is not None else ''
                    }

                    answers.append(val)

                elif question['type'] == 'dropdown':
                    select_query = "SELECT * FROM dropdown_answers WHERE answer_id=%s"
                    cursor.execute(select_query, (a_id,))
                    ddq_id = cursor.fetchone()['dropdown_question_option_id']

                    select_query = "SELECT * FROM dropdown_question_options WHERE dropdown_question_option_id=%s"
                    cursor.execute(select_query, (ddq_id,))

                    val = {
                        'type': 'text',
                        'value': cursor.fetchone()['dropdown_question_option'] or ''
                    }

                    answers.append(val)

                elif question['type'] == 'image':
                    select_query = "SELECT * FROM image_answers WHERE answer_id=%s"
                    cursor.execute(select_query, (a_id,))
                    ans = cursor.fetchone()

                    if ans is None:
                        answers.append({'type': 'none'})
                        continue
                    img = base64.b64encode(ans['answer'])

                    val = {
                        'type': 'image',
                        'value': img.decode('utf-8')
                    }
                    answers.append(val)

            return form_questions, answers, submission_details

        except (psycopg2.Error) as error:
            print(error)
            return False
        
    def get_image(self, user_id, form_id, answer_id):

        try:

            cursor = self.connection.cursor(cursor_factory=RealDictCursor)

            if not self.has_read_access(form_id, user_id):
                return False

            select_query = "SELECT * FROM image_answers WHERE answer_id=%s"
            cursor.execute(select_query, (answer_id,))
            ans = cursor.fetchone()

            if ans is None:
                return False

            img = base64.b64encode(ans['answer'])

            return img.decode('utf-8')

        except (psycopg2.Error) as error:
            print(error)
            return False

if __name__ == '__main__':
    db = Database()
    import json
    print(db.get_all_responses(1, 1))
    db.close()


