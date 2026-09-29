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


## Q
5. Nowwriteaprogramthatuseswait()towaitforthechildprocess to finish in the parent. What does wait() return? What happens if you use wait() in the child?

## Q 
6. Write a slight modification of the previous program, this time us- ing waitpid() instead of wait(). When would waitpid() be useful?

## A

## Q
7. Write a program that creates a child process, and then in the child closes standard output (STDOUT FILENO). What happens if the child calls printf() to print some output after closing the descriptor?

## Q
8. Write a program that creates two children, and connects the stan- dard output of one to the standard input of the other, using the pipe() system call.