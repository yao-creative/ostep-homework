from dataclasses import dataclass, replace
from typing import Dict, List
import string
from optparse import OptionParser
import random
import sys
from typing import Dict, List, Tuple, NewType

ProcessName = NewType("Process", str)
#
# to make Python2 and Python3 act the same -- how dumb
# 
def random_seed(seed):
    try:
        random.seed(seed, version=1)
    except:
        random.seed(seed)
    return

def random_randint(low, hi):
    return int(low + random.random() * (hi - low + 1))

def random_choice(L):
    return L[random_randint(0, len(L)-1)]

@dataclass(frozen=True)
class ForkerConfig:
    fork_percentage: int
    max_actions: int
    action_list: str
    show_tree: bool
    just_final: bool
    leaf_only: bool
    local_reparent: bool
    print_style: str
    solve: bool 


@dataclass
class ForkerState:
    root_name: ProcessName
    process_list: List[ProcessName]
    children: Dict[ProcessName, List[ProcessName]]
    parents: Dict[ProcessName, ProcessName]
    name_length: ProcessName
    base_names: ProcessName
    curr_names: ProcessName
    curr_index: ProcessName


def new_forker_state() -> ForkerState:
    return ForkerState(
        root_name='a',
        process_list=['a'],
        children={'a': []},
        parents={'a': ''},
        name_length=1,
        base_names=string.ascii_lowercase + string.ascii_uppercase,
        curr_names=string.ascii_lowercase + string.ascii_uppercase,
        curr_index=1,
    )

def parse(args: List[str]) -> Tuple[object, List[str]]:
    parser = OptionParser()
    parser.add_option('-s', '--seed', default=-1, help='the random seed', action='store', type='int', dest='seed')
    parser.add_option('-f', '--forks', default=0.7, help='percent of actions that are forks (not exits)', action='store', type='float', dest='fork_percentage')
    parser.add_option('-A', '--action_list_arg', default='', help='action list, instead of randomly generated ones (format: a+b,b+c,b- means a fork b, b fork c, b exit)', action='store', type='string', dest='action_list')
    parser.add_option('-a', '--actions', default=5, help='number of forks/exits to do', action='store', type='int', dest='actions')
    parser.add_option('-t', '--show_tree', help='show tree (not actions)', action='store_true', default=False, dest='show_tree')
    parser.add_option('-P', '--print_style', help='tree print style (basic, line1, line2, fancy)', action='store', type='string', default='fancy', dest='print_style')
    parser.add_option('-F', '--final_only', help='just show final state', action='store_true', default=False, dest='just_final')
    parser.add_option('-L', '--leaf_only', help='only leaf processes exit', action='store_true', default=False, dest='leaf_only')
    parser.add_option('-R', '--local_reparent', help='reparent to local parent', action='store_true', default=False, dest='local_reparent')
    parser.add_option('-c', '--compute', help='compute answers for me', action='store_true', default=False, dest='solve')
    (options, parsed_args) = parser.parse_args(args)
    return options, parsed_args


def new_forker_config(options) -> ForkerConfig:
    return ForkerConfig(
        fork_percentage=options.fork_percentage,
        max_actions=options.actions,
        action_list_arg=options.action_list_arg,
        show_tree=options.show_tree,
        just_final=options.just_final,
        leaf_only=options.leaf_only,
        local_reparent=options.local_reparent,
        print_style=options.print_style,
        solve=options.solve,
    )

# Curr_proc is the current node being visited
# pmask: {0, ..., level - 1} of type Nat -> {0,1} of type Bool.
# Partial function for each ancestor depth if the ancesstor has still undrawn siblings below it.
# pmask[i]=True ⟺ a_i​ is not the last child of its own parent
# the tree is printed level by level breadth first instead of depth first.
def walk(forker_state: ForkerState, forker_config: ForkerConfig, curr_proc: ProcessName, level: int, pmask: Dict[int, bool], is_last: bool) -> None:

    # Pre spacing
    print('                               ', end='')

    # Partition on print_style: str = basic | line1 | line2 | fancy
    # Match basic  to immediate recurse while others use characters to draw the chart.
    if forker_config.print_style == "basic":
        # No lines just space. 
        for i in range(level):
            print('   ', end='')
        print('%2s' % curr_proc)
        for child in forker_state.children[curr_proc]:
            walk(forker_state, forker_config, child, level + 1, {}, False)
        return
    elif forker_config.print_style == 'line1':
        chars = ('|', '-', '+', '|')
    elif forker_config.print_style == 'line2':
        chars = ('|', '_', '|', '|')
    elif forker_config.print_style == 'fancy':
        # these characters taken from 'treelib', a fun printing package for trees
        # https://github.com/caesar0301/treelib
        # chars = ('\u2502', '\u2500', '\u251c', '\u2514')
        chars = (u'\u2502', u'\u2500', u'\u251c', u'\u2514')
    else:
        print('bad style %s' % forker_config.print_style)
        exit(1)
    
    # Tree drawing: if node isn't root then there are branches to nodes above it.
    # print stuff before node
    if level > 0: 
        # main printing
        for i in range(level -1):
            if pmask[i]:
                 # '|  '
                print('%s   ' % chars[0], end='')
            else:
                print('    ', end='')
            if pmask[level-1]:
                # '|__'
                if is_last:
                    print('%s%s%s ' % (chars[3], chars[1], chars[1]), end='')
                else:
                    print('%s%s%s ' % (chars[2], chars[1], chars[1]), end='')
            else:
                # '___' 
                print(' %s%s%s ' % (chars[1], chars[1], chars[1]), end='')

    # print node
    print('%s' % curr_proc)

    # undo parent verticals
    if is_last:
        pmask[level-1] = False

    # recurse
    pmask[level] = True
    for child in forker_state.children[curr_proc][:-1]:
        walk(forker_state, forker_config, child, level + 1, pmask, False)
    for child in forker_state.children[curr_proc][-1:]:
        walk(forker_state, forker_config, child, level + 1, pmask, True)
    return
                

# no return
def print_tree(forker_state: ForkerState, forker_config: ForkerConfig) -> None:
    walk(forker_state, forker_config, forker_state.root_name, 0, {}, False)


def grow_names(forker_state: ForkerState) -> ForkerState:
    new_names = []
    # new_names is of type List(str + str)
    # constructed from curr_names and base_names
    for b1 in forker_state.curr_names:
        for b2 in forker_state.base_names:
            new_names.append(b1 + b2)
    forker_state.curr_names = new_names
    forker_state.curr_index = 0
    return forker_state

def get_name(forker_state: ForkerState) -> Tuple[ProcessName, ForkerState]:
    # maxed out names available
    # amortized name generation
    if forker_state.curr_index == len(forker_state.curr_names):
        forker_state = grow_names(forker_state)
    
    name = forker_state.curr_names[forker_state.curr_index]
    forker_state.curr_index += 1
    return name, forker_state
    



# generative 
# take fork config and generate action list 
def new_action_list(forker_config: ForkerConfig, forker_state:ForkerState) -> List: # action_list
    # bernoulli(N = max_actions, P = fork_percentage)
    action_list = []
    num_actions = 0
    fork_candidate_frontier = [forker_state.root_name]


    # Let N = forker_config.max_actions
    # N -> ((parent x child) | (parent))^N
    # with N \in Natural  and parent, child \in str (which is basically type ProcessName) here.
    while num_actions < forker_config.max_actions:
        if random.random() < forker_config.fork_percentage:
            # FORK:: pick random parent, add child to it
            fork_choice = random_choice(fork_candidate_frontier)
            new_child, forker_state = get_name(forker_state) # mutation on future name bank
            action_list.append('%s+%s' % (fork_choice, new_child))
            fork_candidate_frontier.append(new_child) #new frontier candidate
        else:
            # EXIT:: pick random child, remove it
            #        exception: no killing root process, sorry
            exit_choice = random_choice(fork_candidate_frontier)
            if exit_choice == forker_state.root_name:
                continue
            fork_candidate_frontier.remove(exit_choice)
            action_list.append('%s-' % exit_choice)
        num_actions += 1
    return action_list


# Error exit control.
def handle_bad_action(action) -> None:
    print('bad action (%s), must be X+Y or X- where X and Y are processes' % action)
    exit(1)


        
def handle_check_legal(action) ->  List[str]:
    if '+' in action:
        tmp = action.split('+')
        if len(tmp) != 2:
            handle_bad_action(action)
        return [tmp[0], tmp[1]]
    elif '-' in action:
        tmp = action.split('-')
        if len(tmp) != 2:
            handle_bad_action(action)
        return [tmp[0]]
    else:
        handle_bad_action(action)
    return

# State mutator
def do_fork(forker_state: ForkerState, parent_proc: ProcessName, child_proc: ProcessName) -> Tuple[str|ForkerState]:
    forker_state.process_list.append()
    forker_state.children[child_proc] = []
    forker_state.children[parent_proc].append(child_proc)
    forker_state.parents[child_proc] = parent_proc
    output = '%s forks %s' % (parent_proc, child_proc)
    return output, forker_state


def action_step(action: str, forker_config: ForkerConfig, forker_state: ForkerState) -> ForkerState:
    handle_check_legal(action)
    if 



# driver taking Action* -> terminal tree state in fork_state.
def fold_action_list(action_list: List[str], forker_config: ForkerConfig, forker_state: ForkerState) -> ForkerState:
    for a in action_list:
        forker_state = action_step(a, forker_config, forker_state)
    return forker_state


# effect of emitting into IO without return.
def emit_tree(forker_config: ForkerConfig, forker_state: ForkerState) -> None:
    if forker_config.just_final:
        if forker_config.show_tree:
            print('\n                        Final Process Tree:')
            print_tree(forker_state = forker_state, forker_config = forker_config)
            print('')
        else:
            if forker_config.solve:
                print('\n                        Final Process Tree:')
                print_tree(forker_state = forker_state, forker_config = forker_config)
                print('')
            else:
                print('\n                        Final Process Tree?\n')
        

def run(forker_config: ForkerConfig) -> None:
    forker_state = new_forker_state()
    print('                           Process Tree:')
    print_tree(forker_state = forker_state, forker_config = forker_config)
    print('')

    if forker_config.action_list_arg != '':
        # Use given action list
        action_list = forker_config.action_list_arg.split(',')
    else:
        action_list = new_action_list(forker_config = forker_config, forker_state = forker_state)

    forker_state = fold_action_list(action_list, forker_config, forker_state)
    
    if forker_config.just_final:
        if forker_config.show_tree:
            print('\n                        Final Process Tree:')
            print_tree(forker_state = forker_state, forker_config = forker_config)
            print('')
        else:
            if forker_config.solve:
                print('\n                        Final Process Tree:')
                print_tree(forker_state = forker_state, forker_config = forker_config)
                print('')
            else:
                print('\n                        Final Process Tree?\n')
    return 



        
    

    
    


# 0 -> Program run
def main():
    args = sys.argv[1:]
    (options, parsed_args) = parse(args)

    # Pre run seed
    if options.seed != -1:
        random_seed(options.seed)
    # Prerun config assertion
    if options.fork_percentage <= 0.001:
        print('fork_percentage must be > 0.001')
        exit(1)

    
    config = new_forker_config(options)
    run(config)
   


    print('')
    print('ARG seed', options.seed)
    print('ARG fork_percentage', options.fork_percentage)
    print('ARG actions', options.actions)
    print('ARG action_list', options.action_list)
    print('ARG show_tree', options.show_tree)
    print('ARG just_final', options.just_final)
    print('ARG leaf_only', options.leaf_only)
    print('ARG local_reparent', options.local_reparent)
    print('ARG print_style', options.print_style)
    print('ARG solve', options.solve)
    print('')




if __name__ == '__main__':
    main()
