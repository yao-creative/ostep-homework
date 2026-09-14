
from __future__ import print_function
# from pickle import PERSID
import sys
from optparse import OptionParser
import random
from enum import Enum, auto, nonmember
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
    ON_IO = auto()  # IO_ISSUE Trigger
    ON_END = auto() # IO_DONE Trigger 


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
    code: Tuple[str, ...]      # tuple, not list -> actually mutable
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
class SchedulerMetrics:
    cpu_busy: int
    io_busy: int


def parse(args: List[str]) -> Tuple[object, List[str]]:
    parser = OptionParser()
    parser.add_option('-s', '--seed', default=0, help='the random seed', action='store', type='int', dest='seed')
    parser.add_option('-P', '--program', default='', help='more specific controls over programs', action='store', type='string', dest='program')
    parser.add_option('-l', '--processlist', default='', help='a comma-separated list of processes to run, in the form X1:Y1,X2:Y2,... where X is the number of instructions that process should run, and Y the chances (from 0 to 100) that an instruction will use the CPU or issue an IO (i.e., if Y is 100, a process will ONLY use the CPU and issue no I/Os; if Y is 0, a process will only issue I/Os)', action='store', type='string', dest='process_list')
    parser.add_option('-L', '--iolength', default=5, help='how long an IO takes', action='store', type='int', dest='io_length')
    parser.add_option('-S', '--switch', default='SWITCH_ON_IO', help='when to switch between processes: SWITCH_ON_IO, SWITCH_ON_END', action='store', type='string', dest='process_switch_behavior')
    parser.add_option('-I', '--iodone', default='IO_RUN_LATER', help='type of behavior when IO ends: IO_RUN_LATER, IO_RUN_IMMEDIATE', action='store', type='string', dest='io_done_behavior')
    parser.add_option('-c', help='compute answers for me', action='store_true', default=False, dest='solve')
    parser.add_option('-p', '--printmetrics', help='print statistics at end; only useful with -c flag (otherwise metrics are not printed)', action='store_true', default=False, dest='print_metrics')
    (options, parsed_args) = parser.parse_args(args)
    return options, parsed_args

# 0 -> Scheduler state 
def new_scheduler_state() -> SchedulerState:
    return SchedulerState(proc_info={},
                          curr_proc=0,
                          io_finish_times={},
                          clock_tick=0,
                          io_length=0,
                          io_done=False)

# 0 ->SchedulerMetrics Class
def new_scheduler_statistics() -> SchedulerMetrics:
    return SchedulerMetrics(cpu_busy=0,io_busy=0)

# Options -> Schedulerconfig
def new_scheduler_config_from_options(options):
    switch_name = options.process_switch_behavior.removeprefix('SWITCH_')
    io_done_name = options.io_done_behavior.removeprefix('IO_RUN_')
    return SchedulerConfig(
        process_switch_policy=SchedulerSwitchPolicy[switch_name],
        io_done_policy=IORunPolicy[io_done_name],
        io_length=options.io_length,
    )

# modify in place 
def new_process(scheduler_state: SchedulerState) -> Tuple[SchedulerState, int]:
    proc_id = len(scheduler_state.proc_info)
    scheduler_state.proc_info[proc_id] = ProcessInfo(
        pid=proc_id,
        pc=0,
        code=[],
        state=ProcessState.READY
    )

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
            scheduler_state.proc_info[pid].code.append(Instruction.COMPUTE)
        else:
            scheduler_state.proc_info[pid].code.append(Instruction.IO)
            # add one compute to HANDLE the I/O completion
            scheduler_state.proc_info[pid].code.append(Instruction.IO_DONE)
    return scheduler_state

# Transitions 

# check current state if valid.

# transition to running:
# Transition validity requires that ProcessInfo is equal to current proc info. 
# Only current one can transition.
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


# state readers:
def get_current_proc_info(scheduler_state: SchedulerState) -> ProcessInfo:
    return scheduler_state.proc_info[scheduler_state.curr_proc]

def get_proc_info_by_pid(pid: int, scheduler_state: SchedulerState) -> ProcessInfo:
    return scheduler_state.proc_info[pid]



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
        if get_proc_info_by_pid(pid, scheduler_state).state != ProcessState.DONE:
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


# State Mutators.
def set_proc_info_by_pid(pid: int, proc_info: ProcessInfo, scheduler_state: SchedulerState) -> SchedulerState:
    scheduler_state.proc_info[pid] = proc_info
    return scheduler_state

def set_curr_proc_info(curr_proc_info: ProcessInfo, scheduler_state: SchedulerState) -> SchedulerState:
    scheduler_state.proc_info[scheduler_state.curr_proc] = curr_proc_info
    return scheduler_state


# Update current active process for next time step.
# (curr_proc x  )
def next_proc(scheduler_state: SchedulerState, pid: int = -1) -> SchedulerState:
    # init case, no process id: 
    if pid != -1:
        scheduler_state.curr_proc = pid
        proc_info = get_current_proc_info(scheduler_state)
        new_proc_info = transition_to_running(proc_info, ProcessState.READY)
        return set_proc_info_by_pid(pid, new_proc_info, scheduler_state)
    

    # inductive case first priority process and transition it to running
    # operates on round robin
    # k + 1 -> n 
    for pid in range(scheduler_state.curr_proc + 1, get_num_processes(scheduler_state)):
        if get_proc_info_by_pid(pid, scheduler_state).state == ProcessState.READY:
            scheduler_state.curr_proc = pid
            proc_info = get_current_proc_info(scheduler_state)
            new_proc_info = transition_to_running(proc_info, ProcessState.READY)
            return set_proc_info_by_pid(pid, new_proc_info, scheduler_state) 
    
    # 0 -> k + 1
    for pid in range(0, scheduler_state.curr_proc + 1):
        if get_proc_info_by_pid(pid, scheduler_state).state == ProcessState.READY:
            scheduler_state.curr_proc = pid
            proc_info = get_current_proc_info(scheduler_state)
            new_proc_info = transition_to_running(proc_info, ProcessState.READY)
            return set_proc_info_by_pid(pid, new_proc_info, scheduler_state)

    # No ready anywhere one of (all blocked | all done)
    return scheduler_state
# Resolve done on instructions

def resolve_instructions_done(scheduler_state: SchedulerState) -> SchedulerState:
    curr_proc_info = get_current_proc_info(scheduler_state)
    if len(curr_proc_info.code) == 0 and curr_proc_info.state == ProcessState.RUNNING:
        new_proc_info = transition_to_done(curr_proc_info, ProcessState.RUNNING)
        scheduler_state = set_proc_info_by_pid(scheduler_state.curr_proc, new_proc_info, scheduler_state)
        scheduler_state = next_proc(scheduler_state)
    return scheduler_state


# no state mutation just emit 
def emit_scheduler_state_per_tick(scheduler_state: SchedulerState, curr_instruction: Instruction) -> None:
    # Show tick
    if scheduler_state.io_done:
        print('%3d*' % scheduler_state.clock_tick, end='')
    else:
        print('%3d ' % scheduler_state.clock_tick, end='')
    
    # Map PID:
    # partition on pid = 
    # Case current process -> Show instruction excuted
    # Case not active process -> Show state
    for pid in range(get_num_processes(scheduler_state)):
        if pid == scheduler_state.curr_proc and curr_instruction != '':
            print('%14s' % ('RUN:'+curr_instruction.name), end='')
        else:
            print('%14s' % (get_proc_info_by_pid(pid, scheduler_state).state.name), end='')

def emit_header(scheduler_state: SchedulerState) -> None:
    print('%s' % 'Time', end='')
    for pid in range(get_num_processes(scheduler_state)):
        print('%14s' % ('PID:%2d' % pid), end='')
    print('%14s%14s' % ('CPU', 'IOs'))
    
# Policies based on config.
# Match (IORunPolicy x Pid x Curr_proc.ProcessState (fixed) x Pid.code == IO_DONE (fixed)) in the context.
# (Immediate x (Pid != Curr_proc) x RUNNING x (Pid.code == IO_DONE)) -> (Immediate x (Pid != Curr_proc) x READY x (Pid.code == IO_DONE))

def handle_io_done_process_switching(scheduler_state: SchedulerState, pid: int, scheduler_config: SchedulerConfig) -> SchedulerState:

    # Policy lexicographic ordering on IORunPolicy.IMMEDIATE > SchedulerSwitchPolicy.END
    # immediate switching post termination.
    if scheduler_config.io_done_policy == IORunPolicy.IMMEDIATE:
        # Partition:
        # Case 1: ~(pid = curr_proc) &&  curr_proc.state == Running : 
        # (pid != curr_proc x RUNNING) in (Pids , curr_proc.state) 
        # causes:
        # (curr_proc, RUNNING) -> (curr_proc, READY) so globally count(RUNNING) on PID = 0
        # Case 2: currently active | curr_proc not RUNNING -> pass
        if scheduler_state.curr_proc != pid and get_current_proc_info(scheduler_state).state == ProcessState.RUNNING:
            demoted_proc_info = transition_to_ready( get_current_proc_info(scheduler_state), ProcessState.RUNNING)
            scheduler_state = set_proc_info_by_pid(scheduler_state.curr_proc, demoted_proc_info, scheduler_state)
        # Trigger switch anyways since one IO done.
        # Guarantees (Exists Unique (pid, RUNNING) | Forall (PID, ProcessStates) = (pid, (DONE, BLOCKED)))
        scheduler_state = next_proc(scheduler_state, pid)
    else:
        # LATER
        # Parition twice 
        # Case 1: (ON_END x COUNT(PID where STATE = READY) > 1) in (SchedulerSwitchPolicy x N (Derived from processStates))
        # When finishing IO
        # Case 2: ( True = (ON_END | ON_IO (ineffective here since this is IO issuing action)) x  COUNT(PID where STATE = READY) == 1) in (SchedulerSwitchPolicy x N (Derived from processStates))
        # Case 3: ~(Case 1 && Case 2) = (~ Case 1 | ~ Case 2) 
        # = (ON_IO x COUNT(PID where STATE = READY) <= 1) | (False x COUNT(PID where STATE = READY) != 1)
        # = (ON_IO x COUNT(PID where STATE = READY) > 1)
        # IO is the last case RUNNING (one last current process) or all states are probably DONE.
        if scheduler_config.process_switch_policy == SchedulerSwitchPolicy.ON_END and get_num_runnable(scheduler_state) > 1:
            scheduler_state = next_proc(scheduler_state, pid)
        if get_num_runnable(scheduler_state) == 1:
            scheduler_state = next_proc(scheduler_state, pid)
    return scheduler_state

# Single process IO done:
# x is like &&
# for all pid : 
# (pid x BLOCKED x (io_finish_time == clock_tick)) in (Pids (int) x ProcessState x IO_finish_time (int)) -> (pid x READY x io_finish_time) change only ready dim.
def resolve_io_done(scheduler_state: SchedulerState, pid: int, scheduler_config: SchedulerConfig) -> SchedulerState:
    if scheduler_state.clock_tick in scheduler_state.io_finish_times[pid]:
        new_proc_info = transition_to_ready(get_proc_info_by_pid(pid, scheduler_state), ProcessState.BLOCKED)
        scheduler_state = set_proc_info_by_pid(pid, new_proc_info, scheduler_state)
        scheduler_state = handle_io_done_process_switching(scheduler_state, pid, scheduler_config)
        scheduler_state = resolve_instructions_done(scheduler_state)
    return scheduler_state



def emit_instruction(curr_instruction: Instruction) -> None:
    # Fundamental dependency is curr_instruction == "" if curr_proc.state != RUNNING from handle_execute_instruction and more instructions left.
    # CPU output here: if no instruction executes, output a space, otherwise a 1
    if curr_instruction == '': 
        print("%14s" % " ", end="")
    else:  # COMPUTE | IO_ISSUE | IO_DONE
        print("%14s" % "1", end="")

def emit_outstanding_ios(num_outstanding: int) -> None:
    if num_outstanding > 0:
        print("%14s" % str(num_outstanding), end="")
    else:
        print("%10s" % " ", end="")
    print()

def handle_execute_instructions(scheduler_state: SchedulerState, scheduler_metrics: SchedulerMetrics) -> Tuple[SchedulerState, SchedulerMetrics, Instruction]:
    # if current proc is RUNNING and has an instruction, execute it
    # if (state, code) ∈ RUNNING × (Instruction × Code*):
    #     (state, i :: code) → (state, code, i)
    # otherwise:
    #     identity transition

    curr_instruction = ''
    curr_proc_info = get_current_proc_info(scheduler_state)
    # (Running,c::C) --> (Running,C,c)
    # RUNNING × (Instruction × Code*)
    #     --> RUNNING × Code* × Instruction
    if curr_proc_info.state == ProcessState.RUNNING and len(curr_proc_info.code) > 0:
        curr_instruction = curr_proc_info.code.pop(0)
        scheduler_state= set_curr_proc_info(curr_proc_info=curr_proc_info, scheduler_state=scheduler_state)
    
    return scheduler_state, scheduler_metrics, curr_instruction

# (Current pid x RUNNING x IO) in (Pid x ProcessState x Instruction) -> (curr_pid x BLOCKED x IO)
def handle_io_issue(
    scheduler_state: SchedulerState,
    scheduler_config: SchedulerConfig,
    curr_instruction: Instruction,
) -> SchedulerState:
    # guarded identity: only acts when the instruction just popped was IO
    if curr_instruction != Instruction.IO:
        return scheduler_state
    
    
    curr_proc_info = get_current_proc_info(scheduler_state)
    # RUNNING -> BLOCKED on IO
    new_curr_proc_info = transition_to_wait(curr_proc_info, ProcessState.RUNNING)
    # Rewrite to global scheduler state.
    scheduler_state = set_proc_info_by_pid(scheduler_state.curr_proc, new_curr_proc_info, scheduler_state)
    # Finish Tick: which starts from the next tick so + 1 shift and the io length.
    finish_tick = scheduler_state.clock_tick + scheduler_config.io_length + 1
    # Update finish time tick.
    scheduler_state.io_finish_times[scheduler_state.curr_proc] = scheduler_state.io_finish_times[scheduler_state.curr_proc] + [finish_tick]

    # Update to load next active 
    if scheduler_config.process_switch_policy == SchedulerSwitchPolicy.ON_IO:
        scheduler_state = next_proc(scheduler_state)
    return scheduler_state

# update cpu / io counts based on instruction_executed
# Match (Instruction x cpu_busy (int), io_busy (int)) 
# (CPU x cpu_busy x io_busy) -> (CPU x cpu_busy + 1 x io_busy)
# (IO x cpu_busy x io_busy) -> (CPU x cpu_busy x io_busy + 1)
def accumulate_metrics(
    scheduler_metrics: SchedulerMetrics,
    instruction_executed: Instruction,
    num_io_outstanding: int,
) -> SchedulerMetrics:
    cpu_delta = 1 if instruction_executed != '' else 0
    io_delta = 1 if num_io_outstanding > 0 else 0

    return replace(
        scheduler_metrics,
        cpu_busy=scheduler_metrics.cpu_busy + cpu_delta,
        io_busy=scheduler_metrics.io_busy + io_delta,
    )



def handle_scheduler_step(scheduler_state: SchedulerState, scheduler_metrics: SchedulerMetrics, scheduler_config: SchedulerConfig) -> Tuple[SchedulerState, SchedulerMetrics]:
    # increment clock tick.
    scheduler_state.clock_tick += 1
    scheduler_state.io_done = False


    # PROLOGUE — resolve IO completions from prior ticks
    # this is io done in the last cycle
    for pid in range(get_num_processes(scheduler_state)):
        scheduler_state = resolve_io_done(scheduler_state, pid, scheduler_config)
    

    # DISPATCH — execute exactly one instruction for curr_proc
    # Handle Curr Proc step
    # figure out dag of these three steps. and perhaps the one above.
    scheduler_state, scheduler_metrics, curr_instruction = handle_execute_instructions(scheduler_state, scheduler_metrics)
    num_io_outstanding = get_ios_in_flight(scheduler_state, scheduler_state.clock_tick)

    # OBSERVATION — snapshot and emit BEFORE this dispatch's consequences commit
    # emissions and metrics are tracked at the end of the process like a roof function.
    emit_scheduler_state_per_tick(scheduler_state, curr_instruction)
    emit_instruction(curr_instruction)
    emit_outstanding_ios(num_io_outstanding)
    scheduler_metrics = accumulate_metrics(scheduler_metrics, curr_instruction, num_io_outstanding)

    # EPILOGUE — commit this dispatch's consequences, visible starting next tick
    # issuing for next cycle:
    scheduler_state = handle_io_issue(scheduler_state, scheduler_config, curr_instruction)
    scheduler_state = resolve_instructions_done(scheduler_state)
    return scheduler_state, scheduler_metrics
    
def run(scheduler_state: SchedulerState, scheduler_config: SchedulerConfig) -> Tuple[int, int, int]:
    if get_num_processes(scheduler_state) == 0:
        return (0, 0, 0)
    scheduler_state = next_proc(scheduler_state, pid=0)   # doc2's initial move_to_running(READY)
    emit_header(scheduler_state)
    scheduler_metrics = new_scheduler_statistics()
    while get_num_active(scheduler_state) > 0:
        scheduler_state, scheduler_metrics = handle_scheduler_step(scheduler_state, scheduler_metrics, scheduler_config)
    return (scheduler_metrics.cpu_busy, scheduler_metrics.io_busy, scheduler_state.clock_tick)



def main() -> None:
    args = sys.argv[1:]
    options, parsed_args = parse(args)
    random_seed(options.seed) #not very functional but eh. 

    # free monoid of process specifications.
    scheduler_state = new_scheduler_state()
    scheduler_config = new_scheduler_config_from_options(options)
    if options.program != '':
        for p in options.program.split(':'):
            scheduler_state = load_program(p, scheduler_state)
    else:
        # example process description (10:100,10:100)
        for p in options.process_list.split(','):
            scheduler_state = load(p, scheduler_state)
        
    (cpu_busy, io_busy, clock_tick) = run(scheduler_state, scheduler_config)

    if options.print_metrics:
        print('')
        print('metrics: Total Time %d' % clock_tick)
        print('metrics: CPU Busy %d (%.2f%%)' % (cpu_busy, 100.0 * float(cpu_busy)/clock_tick))
        print('metrics: IO Busy  %d (%.2f%%)' % (io_busy, 100.0 * float(io_busy)/clock_tick))
        print('')




if __name__ == "__main__":
    main()

