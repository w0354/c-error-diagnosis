#include <stdio.h>
struct Student
{
char name[10];
int score;
};
int main(void)
{
struct Student s = {"Tom", 90};
printf("%s %d\n", s->name, s->score);
return 0;
}
