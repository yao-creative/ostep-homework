# Homework (Code)

In this homework, you are to gain some familiarity with the process management APIs about which you just read. Don’t worry – it’s even more fun than it sounds! You’ll in general be much better off if you find as much time as you can to write some code, so why not start now?

# Questions + Answers:

## Q:
1. Write  program that calls fork(). Before calling fork(),have the main process access a variable (e.g., x) and set its value to some- thing (e.g., 100). What value is the variable in the child process? What happens to the variable when both the child and parent change the value of x?

## A:
1. The variable is copied from main process to the child process. both original x= 100. but switching back to main if the variable is switched in child, not copied back to main due to only initial state copy.

```
main pid: 36656 x: 100
child pid: 36657 x: 100
child new x: 30
parent pid: 36656 x: 100
```

## Q
2. Write a program that opens a file (with the open() system call) and then calls fork() to create a new process. Can both the child and parent access the file descriptor returned by open()? What happens when they are writing to the file concurrently, i.e., at the same time?

## A
Yes they do both access the file descriptor however by the time the child reads it the fd pointer is already moved half way down the file and the child process steals it

```
open fd: 3
parent pid: 37480 read from fd: b'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed euismod, nibh nec aliquam tristique, nu'
child pid: 37481 read from fd: b'lla nunc laoreet nunc, at volutpat nisl risus id est. Sed euismod, nibh nec aliquam tristique, nulla'
```

For concurrent writing any of the 200 choose 100 permutations of the writes are permissible as every os.write contends for the inode lock on the actual file in the kernel. by checking Open file descriptions table in Kernel and then resolving with inode objects.

## Q
3. Write another program using fork(). The child process should print “hello”; the parent process should print “goodbye”. You should try to ensure that the child process always prints first; can you do this without calling wait() in the parent?

## A
instead of hello good bye, i created a partition based solution. that child is always allocated front part and parent right after. Initially before fork Answer: ftruncate sets the inode's logical size immediately and synchronously. And then I write independently to each part of the partition. This keeps (write_action, file_byte_index) orthogonal for all WriteActions and 

## Q
4. Write a program that calls fork() and then calls some form of exec() to run the program /bin/ls. See if you can try all of the variants of exec(), including (on Linux) execl(), execle(), execlp(), execv(), execvp(), and execvpe(). Why do you think there are so many variants of the same basic call?

## A
<!-- todo -->

Due to no function over loading: different axes for environment, argument variables to the script execution and 
| $b_c$ | $b_r$ | $b_i$ | Name | Arg | Location | Env | Python signature | glibc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0 | 0 | [execve](https://man7.org/linux/man-pages/man2/execve.2.html) | seq | literal | explicit | yes (syscall wrapper) |
| 0 | 0 | 1 | [execv](https://man7.org/linux/man-pages/man2/execve.2.html) | seq | literal | inherit | yes |
| 0 | 1 | 0 | [execvpe](https://man7.org/linux/man-pages/man3/execvpe.3.html) | seq | PATH | explicit | yes (GNU extension) |
| 0 | 1 | 1 | [execvp](https://man7.org/linux/man-pages/man3/execvp.3.html) | seq | PATH | inherit | yes |
| 1 | 0 | 0 | [execle](https://man7.org/linux/man-pages/man3/execle.3.html) | list | literal | explicit | yes |
| 1 | 0 | 1 | [execl](https://man7.org/linux/man-pages/man3/execl.3.html) | list | literal | inherit | yes |
| 1 | 1 | 0 | - | list | PATH | explicit | no |
| 1 | 1 | 1 | [execlp](https://man7.org/linux/man-pages/man3/execlp.3.html) | list | PATH | inherit | yes |


## Q:
5. Now write a program that uses wait() to waitforthechildprocess to finish in the parent. What does wait() return? What happens if you use wait() in the child?

## A:
```
In Child process-
Process ID: 81880
Hello ! Geeks
Exiting

In parent process-
Terminated child's process id: 81880
Signal number that killed the child process: 0
```
wait returns the exit status of the child 0 on success. 

## Q 
6. Write a slight modification of the previous program, this time using waitpid() instead of wait(). When would waitpid() be useful?



## A:
wait pid would be useful when multiple children and the main process or the waiting process only wants one and a specific one. Normal wait is when any child process terminates.



## Q
7. Write a program that creates a child process, and then in the child closes standard output (STDOUT FILENO). What happens if the child calls printf() to print some output after closing the descriptor?

## A:
file descriptor is uniquely per process table reference of file descriptors to the actual Kernel owned open file descriptors. Hence the child process no longer has reference to the open file descriptor however parent still can access it because of it's own table.

```
Traceback (most recent call last):
  File "/Users/yao/projects/ostep-homework/cpu-api/more-homework-stuff/homework.py", line 270, in <module>
    main()
    ~~~~^^
  File "/Users/yao/projects/ostep-homework/cpu-api/more-homework-stuff/homework.py", line 266, in main
    Q.question7()
    ~~~~~~~~~~~^^
  File "/Users/yao/projects/ostep-homework/cpu-api/more-homework-stuff/homework.py", line 258, in question7
    print("Hello after closing stdout file")
    ~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
OSError: [Errno 9] Bad file descriptor
Exception ignored while flushing sys.stdout:
OSError: [Errno 9] Bad file descriptor
```


## Q
8. Write a program that creates two children, and connects the standard output of one to the standard input of the other, using the pipe() system call.
