#!/usr/bin/env python3
# modify FX3 GPIF config file - alphas and betas only

import datetime
import getopt
import re
import sys

section_name = {
    'Number of states in the state machine': 'NUM STATES',
    'Mapping of user defined state names to state indices': 'STATES MAP',
    'Initial value of early outputs from the state machine.': 'ALPHA',
    'Transition function values used in the state machine.': 'TRANSITION',
    'Table containing the transition information for various states.': 'WAVEDATA',
    'Table that maps state indices to the descriptor table indices.': 'WAVEDATA POSITION',
    'GPIF II configuration register values.': 'REGISTERS',
    'This structure holds all the configuration inputs for the GPIF II.': 'CONFIG'
}

num_states_regex = re.compile(r'^#define CY_NUMBER_OF_STATES (\d+)')
states_map_regex = re.compile(r'^#define (\w+) (\d+)')
wavedata_regex = re.compile(r'{\s*{\s*(0[xX][0-9a-fA-F]+)\s*,\s*(0[xX][0-9a-fA-F]+)\s*,\s*(0[xX][0-9a-fA-F]+)\s*}\s*,\s*{\s*(0[xX][0-9a-fA-F]+)\s*,\s*(0[xX][0-9a-fA-F]+)\s*,\s*(0[xX][0-9a-fA-F]+)\s*}\s*}\s*,?')
wavedata_position_regex = re.compile(r'^[\d,]+$')


def read_gpif_config(infile):
    num_states = None
    states_map = dict()
    wavedata = list()
    wavedata_position = list()

    section = None
    for line in infile:
        line = line.strip()
        if line == '/* Summary':
            section = 'NEWSECTION'
        elif section == 'NEWSECTION':
            section = section_name[line]

        # interesting sections
        elif section == 'NUM STATES':
            m = num_states_regex.match(line)
            if m:
                num_states = int(m.group(1))
        elif section == 'STATES MAP':
            m = states_map_regex.match(line)
            if m:
                states_map[int(m.group(2))] = m.group(1)
        elif section == 'WAVEDATA':
            m = wavedata_regex.match(line)
            if m:
                left = (int(m.group(3), 0) * 0x100000000 + int(m.group(2), 0)) * 0x100000000 + int(m.group(1), 0)
                right = (int(m.group(6), 0) * 0x100000000 + int(m.group(5), 0)) * 0x100000000 + int(m.group(4), 0)
                wavedata.append((left, right))
        elif section == 'WAVEDATA POSITION':
            m = wavedata_position_regex.match(line)
            if m:
                wavedata_position = [int(x.strip()) for x in line.split(',')]

    states = list()
    for idx in range(max(states_map.keys()) + 1):
        states.append(states_map.get(idx, None))

    return num_states, states, wavedata, wavedata_position

def parse_list_string(ls):
    if not ls:
        return None
    ls = ls.lstrip('[').rstrip(']')
    if not ls:
        return list()
    return [int(x.strip()) for x in ls.split(',')]

def read_alphas_and_betas(file):
    alphas_and_betas = list()
    for line in file:
        line = line.rstrip('\n')
        if not line or line.startswith('#'):
            continue
        fields = [x.strip() for x in line.split('\t')]
        idx = int(fields[0])
        state_names = [x.strip() for x in fields[1].split(',')]
        left_state = fields[2] if fields[2] else None
        left_alpha_left = parse_list_string(fields[3])
        left_alpha_right = parse_list_string(fields[4])
        left_beta = parse_list_string(fields[5])
        right_state = fields[6] if fields[6] else None
        right_alpha_left = parse_list_string(fields[7])
        right_alpha_right = parse_list_string(fields[8])
        right_beta = parse_list_string(fields[9])
        alphas_and_betas.append((idx, state_names,
                                 left_state, left_alpha_left, left_alpha_right, left_beta,
                                 right_state, right_alpha_left, right_alpha_right, right_beta))
    return alphas_and_betas

def unpack_field(register, fromidx, toidx=None):
    if toidx is None:
        return (register >> fromidx) & 0x1
    else:
        return (register >> fromidx) & ((1 << (toidx - fromidx)) - 1)

def unpack_register(register):
    valid = unpack_field(register, 95)
    if not valid:
        return None
    beta_deassert = unpack_field(register, 94)
    repeat_count = unpack_field(register, 86, 94)
    beta = unpack_field(register, 54, 86)
    alpha_right = unpack_field(register, 46, 54)
    alpha_left = unpack_field(register, 38, 46)
    f1 = unpack_field(register, 33, 38)
    f0 = unpack_field(register, 28, 33)
    Fd = unpack_field(register, 23, 28)
    Fc = unpack_field(register, 18, 23)
    Fb = unpack_field(register, 13, 18)
    Fa = unpack_field(register,  8, 13)
    next_state = unpack_field(register, 0, 8)
    return beta_deassert, repeat_count, beta, alpha_right, alpha_left, f1, f0, Fd, Fc, Fb, Fa, next_state

def validate_alphas_and_betas(alphas_and_betas, states, wavedata, wavedata_position):
    for idx, row in enumerate(alphas_and_betas):
        if row[0] != idx:
            print('invalid row number - expected', idx, 'found', row[0], file=sys.stderr)
            return False
        wavedata_states = [states[i] for i, x in enumerate(wavedata_position) if x == idx]
        if row[1] != wavedata_states:
            print('states not matching in row', idx, '- expected', wavedata_states, 'found', row[1], file=sys.stderr)
            return False

        r = unpack_register(wavedata[idx][0])
        if r is None:
            if not (row[2] is None and row[3] is None and row[4] is None and row[5] is None):
                print('left register in row', idx, 'should be not valid but it is not -', row[2], row[3], row[4], row[5], file=sys.stderr)
                return False
        else:
            next_state = states[r[11]]
            if row[2] != next_state:
                print('left next state not matching in row', idx, '- expected', next_state, 'found', row[2], file=sys.stderr)
                return False

        r = unpack_register(wavedata[idx][1])
        if r is None:
            if not (row[6] is None and row[7] is None and row[8] is None and row[9] is None):
                print('right register in row', idx, 'should be not valid but it is not -', row[6], row[7], row[8], row[9], file=sys.stderr)
                return False
        else:
            next_state = states[r[11]]
            if row[6] != next_state:
                print('right next state not matching in row', idx, '- expected', next_state, 'found', row[6], file=sys.stderr)
                return False

    return True

def onbits_to_int(bits):
    value = 0
    for bit in bits:
        value |= 1 << bit
    return value

def replace_field(register, fromidx, toidx, value):
    return ((register >> toidx) << toidx |
            (value & ((1 << (toidx - fromidx)) - 1)) << fromidx |
            register & ((1 << fromidx) - 1))

def modify_wavedata(alphas_and_betas, wavedata_in):
    wavedata_out = list()
    for alpha_beta, wavedata in zip(alphas_and_betas, wavedata_in):
        _, _, _, left_alpha_left, left_alpha_right, left_beta, _, right_alpha_left, right_alpha_right, right_beta = alpha_beta
        left_register, right_register = wavedata

        if left_alpha_left is not None:
            left_register = replace_field(left_register, 38, 46, onbits_to_int(left_alpha_left))
        if left_alpha_right is not None:
            left_register = replace_field(left_register, 46, 54, onbits_to_int(left_alpha_right))
        if left_beta is not None:
            left_register = replace_field(left_register, 54, 86, onbits_to_int(left_beta))

        if right_alpha_left is not None:
            right_register = replace_field(right_register, 38, 46, onbits_to_int(right_alpha_left))
        if right_alpha_right is not None:
            right_register = replace_field(right_register, 46, 54, onbits_to_int(right_alpha_right))
        if right_beta is not None:
            right_register = replace_field(right_register, 54, 86, onbits_to_int(right_beta))

        wavedata_out.append((left_register, right_register))

    return wavedata_out

def copy_modified_gpif_config(infile, outfile, wavedata_modified):
    section = None
    wavedata_idx = 0
    for line in infile:
        line_stripped = line.strip()
        if line_stripped == '/* Summary':
            section = 'NEWSECTION'
        elif section == 'NEWSECTION':
            section = section_name[line_stripped]

        elif section == 'WAVEDATA':
            m = wavedata_regex.match(line_stripped)
            if m:
                left_register, right_register = wavedata_modified[wavedata_idx]
                left_low = left_register & ((1 << 32) - 1)
                left_mid = left_register >> 32 & ((1 << 32) - 1)
                left_high = left_register >> 64
                right_low = right_register & ((1 << 32) - 1)
                right_mid = right_register >> 32 & ((1 << 32) - 1)
                right_high = right_register >> 64
                trailing_comma = ',' if line_stripped.endswith(',') else ''
                line = f'    {{{{0x{left_low:08X},0x{left_mid:08X},0x{left_high:08X}}},{{0x{right_low:08X},0x{right_mid:08X},0x{right_high:08X}}}}}{trailing_comma}\n'
                wavedata_idx += 1
        outfile.write(line)
        if 'This file is generated by Gpif2 designer' in line:
            outfile.write(' *\n')
            outfile.write(f' * Waveform alphas and betas modified on {datetime.datetime.now().ctime()}\n')

def main():
    infile = sys.argv[1]
    with open(infile) as inf:
        num_states, states, wavedata, wavedata_position = read_gpif_config(inf)
    alphas_and_betas = read_alphas_and_betas(sys.stdin)
    ok = validate_alphas_and_betas(alphas_and_betas, states, wavedata, wavedata_position)
    if not ok:
        sys.exit(1) 
    wavedata_modified = modify_wavedata(alphas_and_betas, wavedata)
    outfile = infile + '.new'
    with open(infile) as inf:
        with open(outfile, 'w') as outf:
            copy_modified_gpif_config(inf, outf, wavedata_modified)
    print('modified wavedata written to', outfile, file=sys.stderr)


if __name__ == '__main__':
    main()
