#include <stdio.h>
int bigger(int a, int b)
{
if (a > b)
return a;
}
int main(void)
{
printf("%d\n", bigger(2, 9));
return 0;
}
