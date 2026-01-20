import re
import sys
import pdftotext  # 2.1.6 must be used, pdftotext > 2.1.6 has undesired result
import pandas as pd

from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from pathlib import Path


DEFAULT_TIMEOUT = 10
IS_WINDOWS = sys.platform.startswith('win') == 'Windows'
CSV_SEPARATOR = ';' if IS_WINDOWS is True else ','
SPECIAL_ALPHA_CHARS = ' \(\)A-ZÁÉÍÓÚÀÈÌÒÙÇÜÏÑ\'.-'
SPECIAL_ALPHANUMERIC_CHARS = SPECIAL_ALPHA_CHARS + '0-9'

def pdf2str(pdf_file: Path) -> str:
    """
    PURPOSE:

        Convert pdf to text

    MANDATORY ARGUMENTS:

        None
    """
    with open(pdf_file, 'rb') as f:
        pdf = pdftotext.PDF(f)  # pdftotext > 2.1.6 has undesired result
    # read all the text into one string
    # '\n\n' to separate pages in text
    return "\n\n".join(pdf)

def pdf2txt(pdf_file: Path, txt_file: Path) -> None:
    """
    PURPOSE:

        Convert pdf to txt file

    MANDATORY ARGUMENTS:

        None
    """
    text = pdf2str(pdf_file)
    with open(txt_file, 'w') as f:
        f.write(f'{text}')

def coordinates_of(city: str) -> tuple[float]:

    loc = Nominatim(user_agent="GetLoc", timeout=DEFAULT_TIMEOUT).geocode(city)
    if not loc:
        raise ValueError(f'Point \'{city}\' not found')
    return (loc.latitude, loc.longitude)
        
def distance_from_home(home: str, city: str) -> float:

    home_coordinates = coordinates_of(home)
    coords = coordinates_of(city)
    return geodesic(home_coordinates, coords).km

def include_city_in_db(distance_db: dict[str, int], candidate: dict[str, str | list], city: str) -> int:
    # slow method, so let's keep a db just in case city appears more than once

    if city not in distance_db:
        distance_db[city] = round(distance_from_home(candidate['home'], city))
                                
    return distance_db
    

def is_in_df(df: pd.DataFrame, code: str, school_id: int, city_id: int) -> bool:

    df = df[(df['code']==code) & (df['school_id']==school_id) & (df['city_id']==city_id)]
    return not df.empty

def get_index(df: pd.DataFrame, code: str, school_id: int, city_id: int) -> list[int]:

    df = df[(df['code']==code) & (df['school_id']==school_id) & (df['city_id']==city_id)]
    return df.index.to_list()

def is_name_match(name: str, candidate: dict[str, str | list]) -> bool:

    return name.replace(' ', '').upper() == candidate['name'].replace(' ', '').upper()

def get_param_in_match(match, param: str) -> str:

    output = None
    if param in match.groupdict() and match[param]:
        output = match[param].strip()
    
    return output

def parse_offert_pdf(
    file: Path,
    candidate: dict[str, str],
    pattern: dict[str, str],
    check_line: dict[str, str | int],
    df: pd.DataFrame,
    debug: bool=False,
) -> pd.DataFrame:

    distance_db = {}
    text = pdf2str(file)
    lines = text.split('\n')

    # check that this is the pdf
    if not lines[check_line['idx']].strip().startswith(check_line['text']):
        raise RuntimeError(f'Wrong format for file \'{file}\'')

    if debug is True:
        pdf2txt(file, file.with_suffix('.txt'))
    
    for line in lines:
        code_match = pattern['code'].search(line)
        province_match = pattern['province'].search(line)
        school_match = pattern['school'].search(line)

        if code_match:
            code = get_param_in_match(code_match, 'code')
            subject = get_param_in_match(code_match, 'subject')

        if province_match:
            province = get_param_in_match(province_match, 'province').upper()

        if school_match:

            if code in candidate['codes'] and province in candidate['provinces']:
                city = get_param_in_match(school_match, 'city')
                city_id = get_param_in_match(school_match, 'city_id')
                school_name = get_param_in_match(school_match, 'school_name')
                school_id = get_param_in_match(school_match, 'school_id')
                hours = get_param_in_match(school_match, 'hours')
                language = get_param_in_match(school_match, 'language')
                itinerant = get_param_in_match(school_match, 'itinerant')
                type_ = get_param_in_match(school_match, 'type')
                type_ = re.sub(r'\s+', ' ', type_) if type_ else None

                distance_db = include_city_in_db(distance_db, candidate, city)
                distance = 0 if debug is True else distance_db[city]
                row = {'code': code, 'subject': subject,'province': province, 'city': city, 'city_id': city_id, 'distance_km': distance,
                        'school_name': school_name, 'school_id': school_id, 'hours': hours, 'language': language, 'itinerant': itinerant,
                        'type': type_}
                df.loc[len(df)+1] = row

    return df

def parse_result_dificil_pdf(
    file: Path,
    candidate: dict[str, str],
    pattern: dict[str, str],
    check_line: dict[str, str | int],
    df: pd.DataFrame,
    debug: bool=False,
) -> pd.DataFrame:

    idx, last_idx = None, None
    text = pdf2str(file)
    lines = text.split('\n')
    df['groups'] = df['groups'].astype(str)

    # check that this is the pdf
    if not lines[check_line['idx']].strip().startswith(check_line['text']):
        raise RuntimeError(f'Wrong format for file \'{file}\'')

    if debug is True:
        pdf2txt(file, file.with_suffix('.txt'))
    
    for line in lines:

        code_match = pattern['code'].search(line)
        place_match = pattern['place'].search(line)
        candidate_match = pattern['candidate'].search(line)

        if code_match:
            code = get_param_in_match(code_match, 'code')

        if place_match:
            school_id = get_param_in_match(place_match, 'school_id')
            city_id = get_param_in_match(place_match, 'city_id')

            # if this place is in df, then get row index and if it is a new place reset variables
            if is_in_df(df, code, school_id, city_id):
                idx = get_index(df, code, school_id, city_id)

                if len(idx) > 1:
                    raise ValueError(f'Multiple rows with {(code, school_id, city_id)} entries')

                idx = idx[0]
                new_place = True if idx != last_idx else False
                last_idx = idx

                if new_place:
                    groups = {'1': 0, '2': 0, '3': 0}

            else:
                idx = None

        if idx and candidate_match:
            position = get_param_in_match(candidate_match, 'position')
            position = int(position) if position.isdigit() else position
            assigned = get_param_in_match(candidate_match, 'assigned')
            name = get_param_in_match(candidate_match, 'name')
            group = get_param_in_match(candidate_match, 'group')

            if assigned:
                df.at[idx, 'winner'] = position

            if is_name_match(name, candidate):
                df.at[idx, 'you'] = position

            if int(group) < 4:
                groups[group] += 1
            
            df.at[idx, 'total'] = position
            df.at[idx, 'groups'] = f'{groups["1"]}/{groups["2"]}/{groups["3"]}'

    return df

def parse_result_continua_pdf(
    file: Path,
    candidate: dict[str, str],
    pattern: dict[str, str],
    check_line: dict[str, str | int],
    df: pd.DataFrame,
    debug: bool=False,
) -> pd.DataFrame:

    code = None
    info = {}
    df['winner'] = df['winner'].astype('Int64')

    text = pdf2str(file)
    lines = text.split('\n')

    # check that this is the pdf
    if not lines[check_line['idx']].strip().startswith(check_line['text']):
        raise RuntimeError(f'Wrong format for file \'{file}\'')

    if debug is True:
        pdf2txt(file, file.with_suffix('.txt'))
    
    for line in lines:

        code_match = pattern['code'].search(line)
        candidate_match = pattern['candidate'].search(line)
        place_match = pattern['place'].search(line)
        type_match = pattern['type'].search(line)

        if code_match:
            code = get_param_in_match(code_match, 'code')
            subject = get_param_in_match(code_match, 'subject')

        if candidate_match:
            position = get_param_in_match(candidate_match, 'position')
            position = int(position) if position.isdigit() else position
            name = f'{candidate_match["surname"].strip()} {candidate_match["name"].strip()}'

        if type_match:
            type_ = get_param_in_match(type_match, 'type')
            type_ = type_.title() if type_ else type_
            result = get_param_in_match(type_match, 'result')

        if code in candidate['codes']:

            if code not in info:
                info[code] = {}
                info[code]['subject'] = subject
                info[code]['results'] = {}
                info[code]['types'] = {}
                info[code]['candidate_position'] = None
                info[code]['total_positions'] = None

            if type_match:
                info[code]['results'][result] = info[code]['results'][result]+1 if result in info[code]['results'] else 1
                if type_:
                    info[code]['types'][type_] = info[code]['types'][type_]+1 if type_ in info[code]['types'] else 1

            if candidate_match and is_name_match(name, candidate):
                info[code]['candidate_position'] = position

            info[code]['total_positions'] = position

        if place_match:
            school_id = get_param_in_match(place_match, 'school_id')
            city_id = get_param_in_match(place_match, 'city_id')

            # if this place is in df, then get row index
            if is_in_df(df, code, school_id, city_id):
                idx = get_index(df, code, school_id, city_id)

                if len(idx) > 1:
                    raise ValueError(f'Multiple rows with {(code, school_id, city_id)} entries')

                idx = idx[0]
                df.at[idx, 'winner'] = position

                if is_name_match(name, candidate):
                    df.at[idx, 'you'] = 'YES'

    return df, info

def process_args(help_foo):

    if len(sys.argv) not in [2, 3]:
        help_foo()
        raise RuntimeError('Arguments are missing or incorrect')
    
    pdf_offert_file = Path(sys.argv[1])
    pdf_result_file = Path(sys.argv[2]) if len(sys.argv) == 3 else None

    return pdf_offert_file, pdf_result_file

def process_files(
    pdf_offert_file: Path,
    pdf_result_file: Path,
    option: str,
    candidate: dict[str, str],
    offert_pattern: dict[str, str],
    result_pattern: dict[str, str],
    offert_check_line: dict[str, str],
    result_check_line: dict[str, str],
    default_columns: list[str],
    extra_columns: list[str],
    debug=False
):

    if not Path(pdf_offert_file).exists():
        raise FileNotFoundError(f'File \'{pdf_offert_file}\' not found')

    if pdf_result_file and not Path(pdf_result_file).exists():
        raise FileNotFoundError(f'File \'{pdf_result_file}\' not found')

    csv_file = pdf_offert_file.with_suffix('.csv')

    columns = default_columns + extra_columns if pdf_result_file else default_columns
    df = pd.DataFrame(columns=columns)

    print(f'Processing {pdf_offert_file} file ')
    df = parse_offert_pdf(pdf_offert_file, candidate, offert_pattern, offert_check_line, df, debug=debug)

    if pdf_result_file:
        print(f'Processing {pdf_result_file} file ')
        if option == 'dificil':
            df = parse_result_dificil_pdf(pdf_result_file, candidate, result_pattern, result_check_line, df, debug=debug)
        else:
            df, info = \
                parse_result_continua_pdf(pdf_result_file, candidate, result_pattern, result_check_line, df, debug=debug)
            print_info(info)

    df.to_csv(csv_file, sep=CSV_SEPARATOR, index=False)
    print(f'See summary in \'{csv_file}\'')

def print_info(info: dict[str, str | dict]):

    for code in info:

        print(f'Info for {code} - {info[code]["subject"]}:')
        print(f' Your position is {info[code]["candidate_position"]} out of {info[code]["total_positions"]}')
        print(' Number of candidates by participation:')
        for result in info[code]['results']:
            print(f'  - {result}: {info[code]["results"][result]}')
        print(' Number of places by duration:')
        for type_ in info[code]['types']:
            print(f'  - {type_}: {info[code]["types"][type_]}')
        print('')