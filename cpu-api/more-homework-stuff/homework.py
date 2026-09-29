
import os

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
        # execl(path, arg0, arg1, ..., argn, NULL)
        # Execute program with arguments.  The last argument must be NULL.

        # execle(path, arg0, arg1, ..., argn, NULL, envp)
        # Execute program with arguments and environment.  The last argument must be NULL,
        # and the environment is specified as a NULL-terminated array of pointers to
        # null-terminated strings.

        # execlp(file, arg0, arg1, ..., argn, NULL)
        # Execute program with arguments.  The first argument is the name of the
        # program to be executed.  The last argument must be NULL.

        # execv(path, argv)
        # Execute program with arguments.  The argument argv is an array of
        # pointers to null-terminated strings that represent the argument list
        # available to the executed program.

        # execve(path, argv, envp)
        # Execute program with arguments and environment.  The argument argv is an array
        # of pointers to null-terminated strings that represent the argument list
        # available to the executed program.  The argument envp is an array of pointers
        # to null-terminated strings that represent the environment for the executed
        # program.

        # execvp(file, argv)
        # Execute program with arguments.  The first argument is the name of the
        # program to be executed.  The argument argv is an array of pointers to
        # null-terminated strings that represent the argument list available to the
        # executed program.

        # execvpe(file, argv, envp)
        # Execute program with arguments and environment.  The first argument is the name
        # of the program to be executed.  The argument argv is an array of pointers to
        # null-terminated strings that represent the argument list available to the
        # executed program.  The argument envp is an array of pointers to null-terminated
        # strings that represent the environment for the executed program.

        # exec(path, argv=(), env={})
        # Execute program.  The first argument is required and is a string that specifies
        # the path to the program to be executed.  Optionally, the caller may specify
        # arguments and environment variables for the new process

        exec_variants = [os.execl, os.execle, os.execlp, os.execv, os.execve, os.execvp, os.execvpe, os.execv]
        for exec_func in exec_variants:
            exec_func('/bin/ls', '/bin/ls')

        



def main():
    Q = QuestionAPI()

    Q.question4()




if __name__ == '__main__':
    main()
