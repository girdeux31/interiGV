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
SPECIAL_ALPHANUMERIC_CHARS = ' \(\)A-ZÁÉÍÓÚÀÈÌÒÙÇÜÑ1234567890\'.-'
SPECIAL_ALPHA_CHARS = ' \(\)A-ZÁÉÍÓÚÀÈÌÒÙÇÜÑ\'.-'

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

def is_in_df(df: pd.DataFrame, code: str, school_id: int, city_id: int) -> bool:

    df = df[(df['code']==code) & (df['school_id']==school_id) & (df['city_id']==city_id)]
    return not df.empty

def get_index(df: pd.DataFrame, code: str, school_id: int, city_id: int) -> list[int]:

    df = df[(df['code']==code) & (df['school_id']==school_id) & (df['city_id']==city_id)]
    return df.index.to_list()

def parse_offert_pdf(
    file: Path,
    candidate: dict[str, str],
    pattern: dict[str, str],
    check_line: dict[str, str | int],
    df: pd.DataFrame,
    debug: bool=False,
) -> pd.DataFrame:

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
            code = code_match['code'].strip()
            subject = code_match['subject'].strip()

        if province_match:
            province = province_match['province'].strip().upper()

        if school_match:

            if code in candidate['codes'] and province in candidate['provinces']:
                city = school_match['city'].strip()
                city_id = school_match['city_id'].strip()
                school_name = school_match['school_name'].strip()
                school_id = school_match['school_id'].strip()
                hours = school_match['hours'].strip()
                language = school_match['language'].strip() if 'language' in school_match.groupdict() else None
                itinerant = school_match['itinerant'].strip()
                type_ = re.sub(r'\s+', ' ', school_match['type'].strip()) if 'type' in school_match.groupdict() else None
                distance = 0 if debug is True else round(distance_from_home(candidate['home'], city))
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
            code = code_match['code'].strip()
            # subject = code_match['subject'].strip()

        if place_match:
            school_id = place_match['school_id'].strip()
            city_id = place_match['city_id'].strip()

            # if this place is in df, then get row index nad if it is a new place reset variables
            if is_in_df(df, code, school_id, city_id):
                idx = get_index(df, code, school_id, city_id)

                if len(idx) > 1:
                    raise ValueError(f'Multiple rows with {(code, school_id, city_id)} entries')

                idx = idx[0]
                new_place = True if idx != last_idx else False

                if new_place:
                    groups = {'1': 0, '2': 0, '3': 0}
                    your_position = None
                    assigned_position = None

                last_idx = idx

            else:
                idx = None

        if idx and candidate_match:
                position = candidate_match['position'].strip()
                position = int(position) if position.isdigit() else position
                assigned = candidate_match['assigned']
                name = candidate_match['name'].strip()
                # date = candidate_match['date'].strip()
                # time = candidate_match['time'].strip()
                # number = candidate_match['number'].strip().split('/')[-1]
                # ranking = candidate_match['ranking'].strip()
                group = candidate_match['group'].strip()
                # place_id = candidate_match['place_id']

                if assigned:
                    df.loc[idx, 'winner'] = position

                if name.replace(' ', '') == candidate['name'].replace(' ', '').upper():
                    df.loc[idx, 'you'] = position

                if int(group) < 4:
                    groups[group] += 1
                
                df.loc[idx, 'total'] = position
                df.loc[idx, 'groups'] = f'{groups["1"]}/{groups["2"]}/{groups["3"]}'

    return df

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
            pass
            # df = parse_result_continua_pdf(pdf_result_file, candidate, result_pattern, result_check_line, df, debug=debug)

    df.to_csv(csv_file, sep=CSV_SEPARATOR, index=False)
    print(f'See summary in \'{csv_file}\'')
