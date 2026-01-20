import re

from pathlib import Path
from utilsGV import process_files, process_args, SPECIAL_ALPHA_CHARS, SPECIAL_ALPHANUMERIC_CHARS


### USER OPTIONS

# candidate info, please check for typos
# home: your city to get distance from
# name: your name as surnames and then first name (case insensitive)
#       to get your position (only if pdf with final results is included)
# codes: codes to include in summary, check codes = f(your degree) in 
#        https://ceice.gva.es/documents/162909733/385996069/2024-25_%282%29_PROF.+DE+ENSE%C3%91ANZA+SECUNDARI_ESPECIALIDADES+Y+T%C3%8DTULOS.pdf
# provinces: provinces you want to look for (case insensitive), let's keep valencian and castilian names

CANDIDATE = {
    'home': 'Valencia',
    'name': 'Surname1 Surname2 Name',
    'codes': [
        '206', '207', '209', '219', '236', '237', '264', '266', '269', 
        '272', '273', '276', '292', '2A1', '2A4', '2A8', '2A9', '2B6',
    ],  # example for chemical engineer
    'provinces': [
        'ALACANT', 'CASTELLÓ', 'VALÈNCIA',
        'ALICANTE', 'CASTELLÓN', 'VALENCIA',
    ],
}

### END OF USER OPTIONS

DEBUG = False
OPTION = 'dificil'
DEFAULT_COLUMNS = ['code', 'subject', 'province', 'city', 'city_id', 'distance_km',
                    'school_name', 'school_id', 'hours', 'other']
EXTRA_COLUMNS = ['winner', 'you', 'total', 'groups']
OFFERT_CHECK_LINE = {'idx': 1, 'text': 'LLOCS DE DIFÍCIL'}
RESULT_CHECK_LINE = {'idx': 0, 'text': 'PARTICIPANTS I LLOC'}
OFFERT_PATTERN = {}
RESULT_PATTERN = {}

p = f'^ESPECIALIDAD/ESPECIALITAT: (?P<code>[0-9A-Z]{{3}}) (?P<subject>[{SPECIAL_ALPHA_CHARS}]+)'
OFFERT_PATTERN['code'] = re.compile(p, re.MULTILINE | re.ASCII)

province_list = [f'{province.upper()}' for province in CANDIDATE['provinces']]
province_list += [f'{province.title()}' for province in CANDIDATE['provinces']]
province_pattern = '|'.join(province_list)
p = f'^PROVÍNCIA/PROVINCIA: (?P<province>{province_pattern})'
OFFERT_PATTERN['province'] = re.compile(p, re.MULTILINE | re.ASCII)

p = f'^(?P<city>[{SPECIAL_ALPHA_CHARS}]+) - (?P<city_id>\d+) - (?P<school_name>[{SPECIAL_ALPHANUMERIC_CHARS}]+) +(?P<school_id>\d+) +(?P<hours>\d+) +(?P<itinerant>[SINO]+) +(?P<other>.*)'
OFFERT_PATTERN['school'] = re.compile(p, re.MULTILINE | re.ASCII)

p = f'^(?P<position>\d+) +(?P<assigned>-->)? +(?P<name>[{SPECIAL_ALPHA_CHARS}]+) *(?P<date>[0-9/]+) (?P<time>[0-9:]+) +(?P<number>[0-9A-Z/]+) +X? +(?P<ranking>\d+) +[SN]? +[SN] +(?P<group>\d) *(?P<place_id>\d+)?'
RESULT_PATTERN['candidate'] = re.compile(p, re.MULTILINE | re.ASCII)

p = f'^ +(?P<code>[0-9A-Z]{{3}}) (?P<subject>[{SPECIAL_ALPHA_CHARS}]+)'
RESULT_PATTERN['code'] = re.compile(p, re.MULTILINE | re.ASCII)

p = '^ +PUESTO : +(?P<school_id>\d+) +(?P<city_id>\d+)'
RESULT_PATTERN['place'] = re.compile(p, re.MULTILINE | re.ASCII)


def print_help():

    print('')
    print('Usage:')
    print('=====')
    print('')
    print(' python dificilGV.py /path/to/offerts.pdf [/path/to/results.pdf]')
    print('')
    print(' - offerts.pdf: pdf file with place offerts')
    print(' - results.pdf: pdf file with final results (optional, if included more info is shown in summary)')
    print('')
    print(' Download pdfs in \'https://ceice.gva.es/es/web/rrhh-educacion/convocatoria-y-peticion-telematica6\' and ')
    print(' \'https://ceice.gva.es/es/web/rrhh-educacion/resolucion1\'')
    print('')
    print(' Visit GitHub page at https://github.com/girdeux31/interiGV for more info.')
    print('')

if __name__ == '__main__':
    
    if DEBUG is True:
        pdf_offert_file = Path(r'examples/dificil/230929_pue_prov.pdf')
        pdf_result_file = Path(r'examples/dificil/230929_par.pdf')
        if not pdf_result_file.exists():
            pdf_result_file = None
    else:
        pdf_offert_file, pdf_result_file = process_args(print_help)

    process_files(
        pdf_offert_file,
        pdf_result_file,
        OPTION,
        CANDIDATE,
        OFFERT_PATTERN,
        RESULT_PATTERN,
        OFFERT_CHECK_LINE,
        RESULT_CHECK_LINE,
        DEFAULT_COLUMNS,
        EXTRA_COLUMNS,
        debug=DEBUG
    )