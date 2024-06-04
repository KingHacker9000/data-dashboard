import psycopg2, os
from psycopg2.extras import RealDictCursor
import base64
from errors import AppError

class Database:


    def __init__(self, dbname='test', user='postgres', password=os.environ['DB_password'], host='localhost', port='5432') -> None:
        try:
            self.dbname = dbname
            self.user=user
            self.password = password
            self.host = host
            self.port = port
            self.connection = psycopg2.connect(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port
            )
        
        except (Exception, psycopg2.Error) as error:
            print(error)

    def reconnect(self):
        try:
            self.connection = psycopg2.connect(
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port
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
            self.connection.close()
            self.reconnect()
            return None
        
    def sign_up_user(self, google_id, picture_uri, email, name) -> bool:

        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            q = "SELECT * FROM users WHERE email=%s"
            cursor.execute(q, (email,))
            user = cursor.fetchone()
            if user is not None:
                q = "UPDATE users SET google_id=%s, name=%s, google_photo_uri=%s WHERE user_id=%s"
                cursor.execute(q, (google_id, name, picture_uri, user['user_id']))
                self.connection.commit()
                return True
            q = "INSERT INTO users (google_id, name, email, google_photo_uri) VALUES (%s, %s, %s, %s)"
            cursor.execute(q, (google_id, name, email, picture_uri))
            self.connection.commit()
            return True

        except (Exception, psycopg2.Error) as error:
            print(error)
            self.connection.close()
            self.reconnect()
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
            self.connection.close()
            self.reconnect()
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
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)

            select_query = "SELECT * FROM user_role WHERE user_role_id=(SELECT user_role_id FROM forms_access WHERE user_id = %s AND form_id = %s)"
            cursor.execute(select_query, (user_id, form_id))

            role = cursor.fetchone()

            if role is None or role['role_name'] not in ['CREATOR', 'VIEWER']:
                return False
            return True
        except (Exception, psycopg2.Error) as error:
            print(error)
            self.connection.close()
            self.reconnect()
            return False
        


    def get_questions(self, form_id: int, user_id: int) -> list[dict]:
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
                    'type': q['question_type'],
                    'type_id':q['question_type_id'],
                    'position':q['position']
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
            self.connection.close()
            self.reconnect()
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
                    if q['answer']:
                        cursor.execute(insert_query, (form_ans_id, q['answer']))
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
            self.connection.close()
            self.reconnect()
            return False


    def get_all_responses(self, form_id: int, user_id: int, period='at'):

        try:

            cursor = self.connection.cursor(cursor_factory=RealDictCursor)

            if not self.has_read_access(form_id, user_id):
                raise AppError('No Access')
            
            select_query = "SELECT * FROM questions WHERE form_id=%s ORDER BY position"
            cursor.execute(select_query, (form_id,))
            questions = cursor.fetchall()
            form_questions = [q['question_text'] for q in questions]
            questions = [self.get_question(question['question_id']) for question in questions]

            date_opt = {
                'pd': 'AND submitted_at >= CURRENT_DATE',
                'pw': "AND submitted_at >= CURRENT_DATE - INTERVAL '7 days'",
                'py': "AND submitted_at >= CURRENT_DATE - INTERVAL '1 year'",
                'at': ''
            }

            select_query = f"SELECT * FROM form_submissions WHERE form_id=%s {date_opt[period]} ORDER BY submitted_at DESC"
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
            self.connection.close()
            self.reconnect()
            raise AppError('PSQL Error')


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
            if sub is None:
                raise AppError('Submission Does Not Exist')

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
            self.connection.close()
            self.reconnect()
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
            self.connection.close()
            self.reconnect()
            return False
        
    def update_access(self, email, role, form_id):

        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)

            select_query = "SELECT * FROM users WHERE email=%s"
            cursor.execute(select_query, (email,))
            user = cursor.fetchone()

            if user is None:
                self.sign_up_user('', '', email, '')
                #raise AppError(f'User {email} must sign up first')
                select_query = "SELECT * FROM users WHERE email=%s"
                cursor.execute(select_query, (email,))
                user = cursor.fetchone()
            
            select_query = "SELECT * FROM forms_access WHERE user_id=%s and form_id=%s"
            cursor.execute(select_query, (user['user_id'], form_id))
            user_role = cursor.fetchone()

            if user_role is None:
                insert_query = "INSERT INTO forms_access (form_id, user_id, user_role_id) VALUES (%s, %s, %s)"
                cursor.execute(insert_query, (form_id, user['user_id'], role))

            elif user_role['user_role_id'] == role:
                raise AppError(f"User {email} already has this role")
            
            else:
                update_query = "UPDATE forms_access SET user_role_id=%s WHERE form_id=%s AND user_id=%s"
                cursor.execute(update_query, (role, form_id, user['user_id']))
            
            self.connection.commit()
            return True

        except (psycopg2.Error) as error:
            print(error)
            self.connection.close()
            self.reconnect()
            return False
        

    def delete_entry(self, form_id, submission_id):
        
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            select_query = "SELECT * FROM form_answers WHERE form_submission_id=%s"
            cursor.execute(select_query, (submission_id,))
            questions = cursor.fetchall()

            for q in questions:
                question = self.get_question(q['question_id'])
                a_id = q['form_answer_id']

                if question['type'] == 'text':
                    select_query = "DELETE FROM text_answers WHERE answer_id=%s"
                    cursor.execute(select_query, (a_id,))

                elif question['type'] == 'numeric':
                    select_query = "DELETE FROM numeric_answers WHERE answer_id=%s"
                    cursor.execute(select_query, (a_id,))

                elif question['type'] == 'date':
                    select_query = "DELETE FROM date_answers WHERE answer_id=%s"
                    cursor.execute(select_query, (a_id,))

                elif question['type'] == 'coordinates':
                    select_query = "DELETE FROM text_answers WHERE answer_id=%s"
                    cursor.execute(select_query, (a_id,))

                elif question['type'] == 'dropdown':
                    select_query = "DELETE FROM dropdown_answers WHERE answer_id=%s"
                    cursor.execute(select_query, (a_id,))

                elif question['type'] == 'image':
                    select_query = "DELETE FROM image_answers WHERE answer_id=%s"
                    cursor.execute(select_query, (a_id,))
           
            select_query = "DELETE FROM form_answers WHERE form_submission_id=%s"
            cursor.execute(select_query, (submission_id,))

            select_query = "DELETE FROM form_submissions WHERE form_submission_id=%s"
            cursor.execute(select_query, (submission_id,))
            self.connection.commit()

            cursor.close()

        except (psycopg2.Error) as error:
            print(error)
            self.connection.close()
            self.reconnect()
            return False
        

    def duplicate(self, form_id, form_name, user_id):

        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            select_query = "INSERT INTO forms (form_name) VALUES (%s)"
            cursor.execute(select_query, (form_name,))
            self.connection.commit()
            select_query = "SELECT * FROM forms WHERE form_name=%s"
            cursor.execute(select_query, (form_name,))
            new_form_id = cursor.fetchone()['form_id']

            questions = self.get_questions(form_id, user_id)

            for q in questions:
                query = 'INSERT INTO questions (form_id, question_text, question_type_id, position) VALUES (%s, %s, %s, %s)'
                cursor.execute(query, (new_form_id, q['text'], q['type_id'], q['position']))
                self.connection.commit()

                if q['type'] == 'dropdown':
                    select_query = 'SELECT * FROM questions WHERE form_id=%s AND position=%s'
                    cursor.execute(select_query, (new_form_id, q['position']))
                    q_id = cursor.fetchone()['question_id']

                    select_query = 'SELECT * FROM dropdown_question_options WHERE question_id=%s ORDER BY position;' 
                    cursor.execute(select_query, (q['question_id'],))
                    options = cursor.fetchall()

                    for opt in options:
                        insert_query = "INSERT INTO dropdown_question_options (question_id, dropdown_question_option, position) VALUES (%s, %s, %s)"
                        cursor.execute(insert_query, (q_id, opt['dropdown_question_option'], opt['position']))
                        self.connection.commit()
           
            insert_query = "INSERT INTO forms_access (form_id, user_id, user_role_id) VALUES (%s, %s, 1)"
            cursor.execute(insert_query, (new_form_id, user_id))
            self.connection.commit()

            cursor.close()
            return new_form_id

        except (psycopg2.Error) as error:
            print(error)
            self.connection.close()
            self.reconnect()
            return False
        
    def add_option(self, question_id, option_text):
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            print(question_id, 'qid')
            q = "SELECT * FROM dropdown_question_options WHERE question_id=%s ORDER BY position DESC LIMIT 1"
            cursor.execute(q, (question_id,))
            pos = int(cursor.fetchone()['position'])+1

            q = 'INSERT INTO dropdown_question_options (question_id, dropdown_question_option, position) VALUES (%s, %s, %s)'
            cursor.execute(q, (question_id, option_text, pos))
            self.connection.commit()
            cursor.close()

        except (psycopg2.Error) as error:
            print(error)
            self.connection.close()
            self.reconnect()
            return False

    def get_forms(self, user_id):

        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            q = "SELECT * FROM forms_access WHERE user_id=%s AND user_role_id IN (1, 2)"
            cursor.execute(q, (user_id,))
            formrows = cursor.fetchall()

            if formrows is None:
                return []
            
            form_ids = [int(row['form_id']) for row in formrows]

            q = 'SELECT * FROM forms WHERE form_id IN %s'
            cursor.execute(q, (tuple(form_ids),))
            forms = cursor.fetchall()
            cursor.close()
            return forms

        except (psycopg2.Error) as error:
            print(error)
            self.connection.close()
            self.reconnect()
            return []


if __name__ == '__main__':
    db = Database()
    import json
    print(db.get_all_responses(1, 1))
    db.close()


