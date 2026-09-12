
from __future__ import print_function
from pickle import PERSID
import sys
from optparse import OptionParser
import random
from enum import Enum, auto
from dataclasses import dataclass, replace
from typing import Dict, List, Tuple



# to make Python2 and Python3 act the same -- how dumb
def random_seed(seed):
    try:
        random.seed(seed, version=1)
    except:
        random.seed(seed)
    return

# process switch behavior
# SCHED_SWITCH_ON_IO = 'SWITCH_ON_IO'
# SCHED_SWITCH_ON_END = 'SWITCH_ON_END'

# # io finished behavior
# IO_RUN_LATER = 'IO_RUN_LATER'
# IO_RUN_IMMEDIATE = 'IO_RUN_IMMEDIATE'
# # things a process can do
# DO_COMPUTE = 'cpu'
# DO_IO = 'io'
# DO_IO_DONE = 'io_done'

# type classes

# Policies
class IORunPolicy(Enum):
    LATER = auto()
    IMMEDIATE = auto()

class SchedulerSwitchPolicy(Enum):
    ON_IO = auto()
    ON_END = auto()


# Actions/ states within the process.
class Instruction(Enum):
    COMPUTE = auto()
    IO = auto()
    IO_DONE = auto()



# # process states
# STATE_RUNNING = 'RUNNING'
# STATE_READY = 'READY'
# STATE_DONE = 'DONE'
# STATE_WAIT = 'BLOCKED'


# Type states.
# ProcessState = RUNNING | READY | DONE | BLOCKED
class ProcessState(Enum):
    RUNNING = auto()
    READY = auto()
    DONE = auto()
    BLOCKED = auto()


# # members of process structure
# PROC_CODE = 'code_'
# PROC_PC = 'pc_'
# PROC_ID = 'pid_'
# PROC_STATE = 'proc_state_'

# run time data classes

# ---- A: the minimal factor most transitions need -------------------------
 
# Run time mutable dataclass.
@dataclass 
class ProcessInfo:
    pid: int
    pc: int
    code: Tuple[str, ...]      # tuple, not list -> actually immutable
    state: ProcessState

@dataclass(frozen=True)
class SchedulerConfig:
    process_switch_policy: SchedulerSwitchPolicy
    io_done_policy: IORunPolicy
    io_length: int

# Global execution state machine for execution
@dataclass
class SchedulerState:
    proc_info: Dict[int, ProcessInfo]
    curr_proc: int
    io_finish_times: Dict[int, List[int]]
    clock_tick: int
    io_length: int
    io_done: bool

# Result states.
@dataclass
class SchedulerStatistics:
    cpu_busy: int
    io_busy: int
    clock_tick: int


def parse(args: List[str]) -> Tuple[object, List[str]]:
    parser = OptionParser()
    parser.add_option('-s', '--seed', default=0, help='the random seed', action='store', type='int', dest='seed')
    parser.add_option('-P', '--program', default='', help='more specific controls over programs', action='store', type='string', dest='program')
    parser.add_option('-l', '--processlist', default='', help='a comma-separated list of processes to run, in the form X1:Y1,X2:Y2,... where X is the number of instructions that process should run, and Y the chances (from 0 to 100) that an instruction will use the CPU or issue an IO (i.e., if Y is 100, a process will ONLY use the CPU and issue no I/Os; if Y is 0, a process will only issue I/Os)', action='store', type='string', dest='process_list')
    parser.add_option('-L', '--iolength', default=5, help='how long an IO takes', action='store', type='int', dest='io_length')
    parser.add_option('-S', '--switch', default='SWITCH_ON_IO', help='when to switch between processes: SWITCH_ON_IO, SWITCH_ON_END', action='store', type='string', dest='process_switch_behavior')
    parser.add_option('-I', '--iodone', default='IO_RUN_LATER', help='type of behavior when IO ends: IO_RUN_LATER, IO_RUN_IMMEDIATE', action='store', type='string', dest='io_done_behavior')
    parser.add_option('-c', help='compute answers for me', action='store_true', default=False, dest='solve')
    parser.add_option('-p', '--printstats', help='print statistics at end; only useful with -c flag (otherwise stats are not printed)', action='store_true', default=False, dest='print_stats')
    (options, parsed_args) = parser.parse_args(args)
    return options, parsed_args

# 0 -> Scheduler state 
def new_scheduler_state(process_switch_behavior, io_done_behavior, io_length) -> SchedulerState:
    return SchedulerState(proc_info={},
                          curr_proc=0,
                          io_finish_times={},
                          clock_tick=0,
                          process_switch_behavior=process_switch_behavior,
                          io_done_behavior=io_done_behavior,
                          io_length=io_length,
                          io_done=False)

# 0 ->SchedulerStatistics Class
def new_scheduler_statistics() -> SchedulerStatistics:
    return SchedulerStatistics(io_starts=0, io_finishes=0, total_time=0, switches=0)

# Options -> Schedulerconfig
def scheduler_config_from_options(options):
    return SchedulerConfig(
        process_switch_behavior=SchedulerSwitchPolicy(options.process_switch_behavior),
        io_done_behavior=IORunPolicy(options.io_done_behavior),
        io_length=options.io_length,
    )

# modify in place 
def new_process(scheduler_state: SchedulerState) -> Tuple[SchedulerState, int]:
    proc_id = len(scheduler_state.proc_info)
    scheduler_state.proc_info[proc_id] = {}
    scheduler_state.proc_info[proc_id].pc = 0
    scheduler_state.proc_info[proc_id].pid = proc_id
    scheduler_state.proc_info[proc_id].code = []
    scheduler_state.proc_info[proc_id].state = ProcessState.READY

    #corresponding upper layer, although ownership is subjective
    scheduler_state.io_finish_times[proc_id] = []
    return scheduler_state, proc_id


# Exact deterministic version of the code
def load_program(program: str, scheduler_state: SchedulerState) -> SchedulerState:
    # load per processor
    scheduler_state, proc_id = new_process(scheduler_state)
    # Over the free monoid of program.
    for line in program.split(','):
        opcode = line[0]
        # opcode = c | i
        # partition cases of opcode either a Compute or IO
        if opcode == 'c': # compute
            num = int(line[1:])
            for i in range(num):
                scheduler_state.proc_info[proc_id].code.append(Instruction.COMPUTE)
        elif opcode == 'i':
            scheduler_state.proc_info[proc_id].code.append(Instruction.IO)
            # add one compute to HANDLE the I/O completion
            scheduler_state.proc_info[proc_id].code.append(Instruction.IO_DONE)
        else:
            print('bad opcode %s (should be c or i)' % opcode)
            exit(1)
    return scheduler_state


# statistical version of the code. with percentage CPU rest is IO
def load(program_description: str, scheduler_state: SchedulerState) -> SchedulerState:
    # percentage of IO per process
    scheduler_state, pid = new_process(scheduler_state) 
    tmp = program_description.split(':')
    if len(tmp) != 2:
        print('Bad description (%s): Must be number <x:y>' % program_description)
        print('  where X is the number of instructions')
        print('  and Y is the percent change that an instruction is CPU not IO')
        exit(1)

    num_instructions, chance_cpu = int(tmp[0]), float(tmp[1])/100.0
    for i in range(num_instructions):
        if random.random() < chance_cpu:
            SchedulerState.proc_info[pid].code.append(Instruction.COMPUTE)
        else:
            SchedulerState.proc_info[pid].code.append(Instruction.IO)
            # add one compute to HANDLE the I/O completion
            SchedulerState.proc_info[pid].code.append(Instruction.IO_DONE)
    return SchedulerState

# Transitions 

# check current state if valid.

# transition to running:
def transition_to_running(p: ProcessInfo, expected: ProcessState) -> ProcessInfo:
    assert p.state == expected, f"{p.pid}: expected {expected}, got {p.state}"
    return replace(p, state=ProcessState.RUNNING)
 
def transition_to_ready(p: ProcessInfo, expected: ProcessState) -> ProcessInfo:
    assert p.state == expected
    return replace(p, state=ProcessState.READY)
 
def transition_to_wait(p: ProcessInfo, expected: ProcessState) -> ProcessInfo:
    assert p.state == expected
    return replace(p, state=ProcessState.BLOCKED)
 

def transition_to_done(p: ProcessInfo, expected: ProcessState) -> ProcessInfo:
    assert p.state == expected, f"{p.pid}: expected {expected}, got {p.state}"
    return replace(p, state=ProcessState.DONE)
 

def get_current_proc_info(scheduler_state: SchedulerState) -> ProcessInfo:
    return scheduler_state.proc_info[scheduler_state.curr_proc]

def get_proc_info_by_pid(pid: int, scheduler_state: SchedulerState) -> ProcessInfo:
    return scheduler_state.proc_info[pid]


def set_proc_info_by_pid(pid: int, proc_info: ProcessInfo, scheduler_state: SchedulerState) -> SchedulerState:
    scheduler_state.proc_info[pid] = proc_info
    return scheduler_state


def get_num_processes(scheduler_state: SchedulerState) -> int:
    return len(scheduler_state.proc_info)

def get_num_instructions(scheduler_state: SchedulerState, pid: int) -> int:
    return len(scheduler_state.proc_info[pid].code)

def get_instruction(scheduler_state: SchedulerState, pid: int, index: int) -> int:
    return scheduler_state.proc_info[pid].code[index]

def get_num_active(scheduler_state: SchedulerState) -> int:
    # find the number of processes with state ~(DONE) = BLOCKED | READY | RUNNING
    num_active = 0
    for pid in range(len(scheduler_state.proc_info)):
        if scheduler_state.proc_info[pid].state != ProcessState.DONE:
            num_active += 1
    return num_active

def get_num_runnable(scheduler_state: SchedulerState) -> int:
    # Find the number of states which can transition into runnable
    # COUNT(READY | RUNNING)
    num_active = 0
    for pid in range(len(scheduler_state.proc_info)):
        if scheduler_state.proc_info[pid].state == ProcessState.READY or \
                scheduler_state.proc_info[pid].state == ProcessState.RUNNING:
            num_active += 1
    return num_active

def get_ios_in_flight(scheduler_state: SchedulerState, current_time: int) -> int:
    # count(outbound IOs) which haven't been finished
    num_in_flight = 0
    for pid in range(len(scheduler_state.proc_info)):
        for t in scheduler_state.io_finish_times[pid]:
            if t > current_time:
                num_in_flight += 1
    return num_in_flight

def space(num_columns) -> None:
    for _ in range(num_columns):
        print('%10s' % ' ', end='')

def next_proc(scheduler_state: SchedulerState, pid: int = -1) -> SchedulerState:
    # init case, no process id: 
    if pid != -1:
        scheduler_state.curr_proc = pid
        proc_info = get_current_proc_info(scheduler_state)
        new_proc_info = transition_to_running(proc_info, ProcessState.READY)
        return set_proc_info_by_pid(pid, new_proc_info, scheduler_state)
    

    # Constructor first priority process and transition it to running 
    for pid in range(scheduler_state.curr_proc + 1, get_num_processes(scheduler_state)):
        if scheduler_state.proc_info[pid].state == ProcessState.READY:
            scheduler_state.curr_proc = pid
            proc_info = get_current_proc_info(scheduler_state)
            new_proc_info = transition_to_running(proc_info, ProcessState.READY)
            return set_proc_info_by_pid(pid, new_proc_info, scheduler_state) 
    
    for pid in range(0, scheduler_state.curr_proc + 1):
        if proc_info[pid].state == ProcessState.READY:
            scheduler_state.curr_proc = pid 
            proc_info = get_current_proc_info(scheduler_state)
            new_proc_info = transition_to_running(proc_info, ProcessState.READY)
            return set_proc_info_by_pid(pid, new_proc_info, scheduler_state)

# resolve running to done
def resolve_done(scheduler_state: SchedulerState) -> SchedulerState:
    curr_proc_info = get_current_proc_info(scheduler_state)
    # take if (curr_proc.state) == running  then (curr_proc.state) = done
    if len(curr_proc_info.code) == 0 and curr_proc_info.state == ProcessState.RUNNING:
        transition_to_done(curr_proc_info, ProcessState.RUNNING)
        scheduler_state = next_proc(scheduler_state)
    return scheduler_state


# based on config
def handle_process_switching(scheduler_state: SchedulerState, pid: int, scheduler_config: SchedulerConfig) -> SchedulerState:
    # immediate switching post termination.
    # ImmediateSwitch && ~(pid = curr_proc) so pid isn't currently active &&  curr_proc.state == Running
    if scheduler_config.io_done_behavior == IORunPolicy.IMMEDIATE and scheduler_state.curr_proc != pid and get_current_proc_info(scheduler_state).state == ProcessState.RUNNING:
        # pid state transition (Running -> Ready)
        scheduler_state = transition_to_ready(get_proc_info_by_pid(pid, scheduler_state), ProcessState.RUNNING)
    else:
        # IO_RUN_LATER
        if scheduler_config.process_switch_behavior == SchedulerSwitchPolicy.ON_END:
            scheduler_state = next_proc(scheduler_state, pid)
        if get_num_runnable(scheduler_state) == 1:
            scheduler_state = next_proc(scheduler_state, pid)


        
# single tick event driven transition for a single process
def handle_process_step(scheduler_state: SchedulerState, pid: int, scheduler_config: SchedulerConfig) -> SchedulerState:
    # resolve IO
    if scheduler_state.clock_tick in scheduler_state.io_finish_times[pid]:
        # if IO finishing now (pid, BLOCKED)-> (pid, READY)
        scheduler_state = transition_to_ready(get_proc_info_by_pid(scheduler_state, pid), ProcessState.BLOCKED)
        handle_process_switching(scheduler_state, pid, scheduler_config)
        resolve_done(scheduler_state)

def handle_scheduler_step(scheduler_state: SchedulerState, scheduler_stats: SchedulerStatistics, scheduler_config: SchedulerConfig) -> Tuple[SchedulerState, SchedulerStatistics]:
    # increment clock tick.
    scheduler_state.clock_tick += 1
    # this is io done in the last cycle
    scheduler_state.io_done = False
    for pid in range(get_num_processes(scheduler_state)):
        scheduler_state = handle_process_step(scheduler_state, pid) 

    
    

def run(scheduler_state: SchedulerState, scheduler_config: SchedulerConfig) -> Tuple[int, int, int]:
    # base case no processors
    if len(scheduler_state.proc_info) == 0:
        return
    
    # inductive case:
    scheduler_stats = new_scheduler_statistics()
    # iterate until all processes finish 
    while scheduler_state.get_num_active() > 0:
        scheduler_state, scheduler_stats = handle_scheduler_step(scheduler_state, scheduler_stats, scheduler_config)


    



def main() -> None:
    args = sys.argv[1:]
    options, parsed_args = parse(args)
    random_seed(options.seed) #not very functional but eh. 

    

    # free monoid of process specifications.
    scheduler_state = new_scheduler_state()
    if options.program != '':
        for p in options.program.split(':'):
            scheduler_state = load_program(p, scheduler_state)
    else:
        # example process description (10:100,10:100)
        for p in options.process_list.split(','):
            scheduler_state = load(p, scheduler_state)
        
    (cpu_busy, io_busy, clock_tick) = run(scheduler_state)



    
    if options.print_stats:
        print('')
        print('Stats: Total Time %d' % clock_tick)
        print('Stats: CPU Busy %d (%.2f%%)' % (cpu_busy, 100.0 * float(cpu_busy)/clock_tick))
        print('Stats: IO Busy  %d (%.2f%%)' % (io_busy, 100.0 * float(io_busy)/clock_tick))
        print('')




if __name__ == "__main__":
    main()

