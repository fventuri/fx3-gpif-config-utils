#!/usr/bin/env python3
# print FX3 GPIF config file

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


def read_gpif_config(file):
    num_states = None
    states_map = dict()
    wavedata = list()
    wavedata_position = list()

    section = None
    for line in file:
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

def onbits(value):
    bits = list()
    count = 0
    while value:
        if value % 2:
            bits.append(count)
        value //= 2
        count += 1
    return bits

def print_register(left_or_right, register, states):
    r = unpack_register(register)
    if r is None:
        return
    beta_deassert, repeat_count, beta, alpha_right, alpha_left, f1, f0, Fd, Fc, Fb, Fa, next_state = r
    print(left_or_right, 'BETA_DEASSERT:', beta_deassert)
    print(left_or_right, 'REPEAT_COUNT:', repeat_count)
    print(left_or_right, 'Beta:', onbits(beta))
    print(left_or_right, 'Alpha_Right:', onbits(alpha_right))
    print(left_or_right, 'Alpha_Left:', onbits(alpha_left))
    print(left_or_right, 'f1:', f1)
    print(left_or_right, 'f0:', f0)
    print(left_or_right, 'Fd:', Fd)
    print(left_or_right, 'Fc:', Fc)
    print(left_or_right, 'Fb:', Fb)
    print(left_or_right, 'Fa:', Fa)
    print(left_or_right, 'NEXT_STATE:', next_state, f'({states[next_state]})')

def print_everything(num_states, states, wavedata, wavedata_position):
    print('num states:', num_states)
    print('states:', states)
    print('wavedata:')
    for row in wavedata:
        print(hex(row[0]), hex(row[1]))
    print('wavedata position:', wavedata_position)

    print()

    for idx, row in enumerate(wavedata):
        wavedata_states = [states[i] for i, x in enumerate(wavedata_position) if x == idx]
        print(f'wavedata[{idx}] - states:', ', '.join(wavedata_states))
        print_register('left', row[0], states)
        print_register('right', row[1], states)
        print('--------------------------------------------------------------------------------')
        #print()

def print_alphas_and_betas(num_states, states, wavedata, wavedata_position):
    for idx, row in enumerate(wavedata):
        wavedata_states = [states[i] for i, x in enumerate(wavedata_position) if x == idx]
        r = unpack_register(row[0])
        if r is None:
            left_alpha_left, left_alpha_right, left_beta, left_next = '', '', '', ''
        else:
            _, _, beta, alpha_right, alpha_left, _, _, _, _, _, _, next_state = r
            left_alpha_left = str(onbits(alpha_left))
            left_alpha_right = str(onbits(alpha_right))
            left_beta = str(onbits(beta))
            left_next = states[next_state]
        r = unpack_register(row[1])
        if r is None:
            right_alpha_left, right_alpha_right, right_beta, right_next = '', '', '', ''
        else:
            _, _, beta, alpha_right, alpha_left, _, _, _, _, _, _, next_state = r
            right_alpha_left = str(onbits(alpha_left))
            right_alpha_right = str(onbits(alpha_right))
            right_beta = str(onbits(beta))
            right_next = states[next_state]
        wavedadata_states_display = f'{", ".join(wavedata_states):24}'
        print('\t'.join((str(idx), wavedadata_states_display,
                         f'{left_next:10}', left_alpha_left, left_alpha_right, left_beta,
                         f'{right_next:10}', right_alpha_left, right_alpha_right, right_beta)))


def main():
    alphas_and_betas = False
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'a')
    except getopt.GetoptError as err:
        print(err)
        sys.exit(1)
    for o, a in opts:
        if o == '-a':
            alphas_and_betas = True
        else:
            assert False, "unhandled option"

    with open(args[0]) as f:
        num_states, states, wavedata, wavedata_position = read_gpif_config(f)
    if alphas_and_betas:
        print_alphas_and_betas(num_states, states, wavedata, wavedata_position)
    else:
        print_everything(num_states, states, wavedata, wavedata_position)

if __name__ == '__main__':
    main()
