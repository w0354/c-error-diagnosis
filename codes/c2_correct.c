#include <stdio.h>
void swap(int *x, int *y)
{
int t = *x;
*x = *y;
*y = t;
}
int main(void)
{
int a = 1, b = 2;
swap(&a, &b);
printf("%d %d\n", a, b);
return 0;
}
