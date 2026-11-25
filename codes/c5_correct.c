#include <stdio.h>
int max(int a, int b)
{
if (a > b)
return a;
else
return b;
}
int main(void)
{
printf("%d\n", max(3, 7));
return 0;
}
