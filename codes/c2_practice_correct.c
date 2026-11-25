#include <stdio.h>
void addTen(int *n)
{
*n = *n + 10;
}
int main(void)
{
int score = 60;
addTen(&score);
printf("%d\n", score);
return 0;
}
