import random


def create_ordered_id_list(df_los):
    """Return the list of patient IDs for that has been sampled uniformly based on
    length of stay's occuring in the data.

    Parameters
    ----------
    df_los : pd.DataFrame
        dataframe containing enc_id and
    """

    length_enc_id_dict = {}
    for _, row in df_los.iterrows():
        length = row["length_of_stay"]
        if length not in length_enc_id_dict:
            length_enc_id_dict[length] = []
        length_enc_id_dict[length].append(row["enc_id"])

    for key in length_enc_id_dict:
        random.shuffle(length_enc_id_dict[key])

    ordered_ids = []
    while length_enc_id_dict:
        length = random.choice(list(length_enc_id_dict.keys()))
        ordered_ids.append(length_enc_id_dict[length].pop(0))
        if not length_enc_id_dict[length]:
            length_enc_id_dict.pop(length)

    return ordered_ids


def divide_ids_among_students(students, department_id_dict, overlap_rounds=5):
    """Take a list with students, and a dict with departments and ids
    divide the ids among the students such that every overlap_rounds all
    students get the same id for the department.

    Parameters
    ----------
    students : list
        list of students
    department_id_dict : dict
        dict with department as key and list of ids as value

    Returns
    -------
    dict
        dict with student as key and list of ids as value
    """

    student_id_dict = {}
    student_dept_dict = {}
    for student in students:
        student_id_dict[student] = []
        student_dept_dict[student] = []

    # For determining when an overlapping id needs to be assigned
    department_overlap_dict = {}
    for dep in department_id_dict:
        department_overlap_dict[dep] = overlap_rounds

    empty_dep = False
    while not empty_dep:
        for id in department_id_dict:
            if department_overlap_dict[id] // overlap_rounds > 0:
                id_to_add = department_id_dict[id].pop(0)
                department_overlap_dict[id] -= overlap_rounds

                # stop when one of the departments has no more ids to assign
                if not department_id_dict[id]:
                    empty_dep = True

                for student in students:
                    student_id_dict[student].append(id_to_add)
                    student_dept_dict[student].append(id)
            else:
                for student in students:
                    id_to_add = department_id_dict[id].pop(0)
                    department_overlap_dict[id] += 1

                    # stop when one of the departments has no more ids to assign
                    if not department_id_dict[id]:
                        empty_dep = True
                        break

                    student_id_dict[student].append(id_to_add)
                    student_dept_dict[student].append(id)

    return student_id_dict, student_dept_dict
