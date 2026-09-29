
import os
import sys
import time



class QuestionAPI:
    def __init__(self):
        pass 
    
    @staticmethod
    def question1():
        x = 100

        print("main pid:", os.getpid(), "x:", x)

        pid = os.fork()

        # Diamond in the single threaded python interpreter here.
        if pid == 0: #fork success
            # child process
            print("child pid:", os.getpid(), "x:", x)
            x = 30
            
            # os._exit(0)
            print("child new x:", x)
            
            # Infinite loop blocks the os.waitpid later
            # while True:
            #     pass

        else: #fork in parent
            # parent process, already executes wait pid whil
            # above if is working in a different process
            # inter process sync
            os.waitpid(pid, 0) 
            # After above if is done the wait unblocks.

            print("parent pid:", os.getpid(), "x:", x)

    @staticmethod
    def question2():
        # open file, get file descriptor
        fd = os.open("concurrent-read.md", os.O_RDONLY)
        print("open fd:", fd)
        
        
        pid = os.fork()

        if pid == 0: #child
            print("child pid:", os.getpid(), "read from fd:", os.read(fd, 100))
        else: #parent
            print("parent pid:", os.getpid(), "read from fd:", os.read(fd, 100))
        os.close(fd)

    @staticmethod
    def question2_1():
        fd = os.open("concurrent-write.md", os.O_RDWR | os.O_APPEND)
        
        pid = os.fork()
        if pid == 0: #child
            print("child fd:", fd)
            for _ in range(100):
                os.write(fd, b"Child\n")
         
        else: #parent
            print("parent fd:", fd)
            for _ in range(100):
                os.write(fd, b"Parent\n")
            
        os.close(fd)



    @staticmethod
    def question3():
        child_line, parent_line = b"Child\n", b"Parent\n"
        n = 100
        fd = os.open("concurrent-write-by-partition.md", os.O_RDWR)   # no O_APPEND

        # last index of file before append
        # fstat: File Descriptors -> file_descriptor_metadata
        base = os.fstat(fd).st_size
        
        
        c_start = base
        p_start = base + n * len(child_line)

        # ftruncate(fd, length)
        # ftruncate(fd, length=0) to truncate to 0 bytes
        os.ftruncate(fd, p_start + n * len(parent_line))  # size once, before fork

        pid = os.fork()
        if pid == 0:
            for k in range(n):

                # pwrite(fd, buf, offset):
                #     fd: file descriptor
                #     buf: bytes to write
                #     offset: position in file where to write
                # Returns number of bytes written.

                os.pwrite(fd, child_line, c_start + k * len(child_line))
        else:
            for k in range(n):
                os.pwrite(fd, parent_line, p_start + k * len(parent_line))
        os.close(fd)
    
    @staticmethod
    def question4():
        # execl(path: str, arg0: str, arg1: str, *args: str, None) -> NoReturn
        # Execute program with arguments.  The last argument must be None.

        # execle(path: str, arg0: str, arg1: str, *args: str, envp: Optional[List[str]]=None) -> NoReturn
        # Execute program with arguments and environment.  The last argument must be None,
        # and the environment is specified as a list of null-terminated strings.

        # execlp(file: str, arg0: str, arg1: str, *args: str, None) -> NoReturn
        # Execute program with arguments.  The first argument is the name of the
        # program to be executed.  The last argument must be None.

        # execv(path: str, argv: List[str]) -> NoReturn
        # Execute program with arguments.  The argument argv is an list of
        # strings that represent the argument list available to the executed program.

        # execve(path: str, argv: List[str], envp: Optional[List[str]]=None) -> NoReturn
        # Execute program with arguments and environment.  The argument argv is an list of
        # strings that represent the argument list available to the executed program.  The
        # argument envp is an list of strings that represent the environment for the executed
        # program.

        # execvp(file: str, argv: List[str]) -> NoReturn
        # Execute program with arguments.  The first argument is the name of the
        # program to be executed.  The argument argv is an list of strings that represent
        # the argument list available to the executed program.

        # execvpe(file: str, argv: List[str], envp: Optional[List[str]]=None) -> NoReturn
        # Execute program with arguments and environment.  The first argument is the name
        # of the program to be executed.  The argument argv is an list of strings that
        # represent the argument list available to the executed program.  The argument envp
        # is an list of strings that represent the environment for the executed program.

        # exec(path: str, argv: List[str]=[], env: Dict[str, str]={}) -> NoReturn
        # Execute program.  The first argument is required and is a string that specifies
        # the path to the program to be executed.  Optionally, the caller may specify
        # arguments and environment variables for the new process
         

         # e is environment
         # l is argument listing dynamic or fixed
         # p 

        # TODO don't really get the file part 
        PRINTENV = "/usr/bin/printenv"          # literal path, used by the non-p variants
        ENV_EXPLICIT = {"GREETING": "explicit"}  # an environment value, chosen by the caller
        # p-variants under Python search PATH of the env you pass, so include PATH
        ENV_EXPLICIT_P = {"PATH": os.environ.get("PATH", "/bin:/usr/bin"), "GREETING": "explicit"}
        def run_in_child(code, name, exec_call):
            """fork, run exec_call in the child, wait in the parent.
            exec never returns on success, so each variant needs its own process."""
            sys.stdout.flush()  # flush before fork so the buffer is not duplicated
            pid = os.fork()
            if pid == 0:
                try:
                    exec_call()
                except OSError as e:
                    print(f"{code} {name}: exec failed: {e}", file=sys.stderr)
                finally:
                    os._exit(127)  # reached only if exec failed
            os.waitpid(pid, 0)

        # code = (collect, resolve, inherit), bit 1 = adapter engaged
        VARIANTS = [
            # 000: seq argv, literal path, explicit env  (the primitive)
            ("000", "execve",  lambda: os.execve(PRINTENV, ["printenv", "GREETING"], ENV_EXPLICIT)),
            # 001: seq argv, literal path, inherit env
            ("001", "execv",   lambda: os.execv(PRINTENV, ["printenv", "GREETING"])),
            # 010: seq argv, PATH search, explicit env
            ("010", "execvpe", lambda: os.execvpe("printenv", ["printenv", "GREETING"], ENV_EXPLICIT_P)),
            # 011: seq argv, PATH search, inherit env
            ("011", "execvp",  lambda: os.execvp("printenv", ["printenv", "GREETING"])),
            # 100: variadic argv, literal path, explicit env (env is the LAST positional arg)
            ("100", "execle",  lambda: os.execle(PRINTENV, "printenv", "GREETING", ENV_EXPLICIT)),
            # 101: variadic argv, literal path, inherit env
            ("101", "execl",   lambda: os.execl(PRINTENV, "printenv", "GREETING")),
            # 110: variadic argv, PATH search, explicit env (Python only, absent from glibc)
            ("110", "execlpe", lambda: os.execlpe("printenv", "printenv", "GREETING", ENV_EXPLICIT_P)),
            # 111: variadic argv, PATH search, inherit env
            ("111", "execlp",  lambda: os.execlp("printenv", "printenv", "GREETING")),
        ]

        os.environ["GREETING"] = "inherited"  # what the inherit variants will see
        for code, name, exec_call in VARIANTS:
            print(f"{code} {name:8s} ->", end=" ")
            run_in_child(code, name, exec_call)

    @staticmethod
    def question5():
        # Wait for the child process to finish in the parent:
        pid = os.fork()
        if pid == 0:
            print("In Child process-")
            time.sleep(3)  # wait a second in the child, so we can see the parent run first
            
            print("Process ID:", os.getpid())
            print("Hello ! Geeks")
            print("Exiting")
        else:
            """
            Condition: ThereExists child process terminate
            os.wait() -> (pid, status)

            Wait for completion of a child process.

            Return a tuple containing process ID and exit status of the child.

            The calling process will be blocked until the child process whose
            process ID is pid has changed state.  If pid is 0, wait for any child
            process.  If pid is less than -1, wait for any child process whose
            process group is equal to the absolute value of pid.

            The status argument is the exit status (supplied to os._exit(), exit(),
            or return) of the process that terminated, converted to an integer.  A
            value of zero represents no error.  On sysV systems, the status argument
            is the low order 8 bits of the status returned by wait(2).  On BSD
            systems, the status argument is the full status value returned by wait(2).
            """

            status = os.wait()
            print("\nIn parent process-")
            print("Terminated child's process id:", status[0])
            print("Signal number that killed the child process:", status[1])

    @staticmethod
    def question6():
        # Wait for the child process to finish in the parent:
        pid = os.fork()
        if pid == 0:
            print("In Child process-")
            time.sleep(3)  # wait a second in the child, so we can see the parent run first
            
            print("Process ID:", os.getpid())
            print("Hello ! Geeks")
            print("Exiting")
        else:
            status = os.waitpid(pid, 0)
            print("\nIn parent process-")
            print("Terminated child's process id:", status[0])
            print("Signal number that killed the child process:", status[1])

    @staticmethod
    def question7():
        pid = os.fork()
        if pid == 0: 
            print("In Child process-")
            os.close(1)  # close STDOUT_FILENO
            print("Hello after closing stdout file")
        else:
            time.sleep(2)

            print("main still can print huh")

    
    @staticmethod
    def question8():
        """
        dup(old_fd: int) -> int
        
        Return a new file descriptor that is a duplicate of the one provided.
        
        Parameters:
            old_fd (int): The file descriptor to duplicate.
        
        Returns:
            int: A new file descriptor that refers to the same file as the original.
        """

        """
        pipe() -> (read_fd: int, write_fd: int)
        
        Create a pipe.
        
        Returns:
            tuple: A tuple containing the read file descriptor and the write file descriptor of the pipe.
        """
        
        """
        dup2(old_fd: int, new_fd: int) -> None
        
        Duplicate file descriptor old_fd to new_fd.
        
        Parameters:
            old_fd (int): The existing file descriptor to duplicate.
            new_fd (int): The new file descriptor that will refer to the same file as old_fd.
        
        Returns:
            None
        """




        # create pipe file descriptors
        r, w = os.pipe()
        
        pid = os.fork()
        pid2 = os.fork()
        if pid == 0: 
            print("In Child process- 1")     
            os.close(r)       
            print("Process ID:", os.getpid())
            print("Hello ! first child")

            message = b"hello hidden child 2 process from child 1 process\n"
            os.write(w, message)

            print(f"closing child1-child2 channel")
            os.close(w)
            print("Exiting first child")

            os._exit(0)

        elif pid2 == 0:
            #does not write to pipe. 
            os.close(w)
            print("In Child process- 2")      
            # 3. Wire the pipe's read end to standard input (file descriptor 0)
            os.dup2(r, 0)    
            # Now, any standard input read (like sys.stdin or input()) pulls from the parent
            data = sys.stdin.read()  
            os.write(1, f"Child 2 processed: {data.upper()}".encode())
            os._exit(0)

        else:
            
            os.waitpid(pid, 0)
            os.waitpid(pid2, 0)

            print("\nIn parent process-")
            

    

    # Check if the caller stack terminates the forked child or not.
    @staticmethod
    def question9():

        def inner_fork():
            pid = os.fork()
            if pid == 0: 
                print("In Child process-")
                time.sleep(3)  # wait a second in the child, so we can see the parent run first
                
                print("Process ID:", os.getpid())
                print("Hello ! Geeks")
                print("Exiting")
            else:
                status = os.waitpid(pid, 0)
                print("\nIn parent process-")
                print("Terminated child's process id:", status[0])
                print("Signal number that killed the child process:", status[1])
            

        print("outer print with Process ID: ",  os.getpid())





def main():
    Q = QuestionAPI()
    Q.question8()


if __name__ == '__main__':
    main()
