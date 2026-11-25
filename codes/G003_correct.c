#include <stdio.h>
int main(void)
{
int i, j;
char z;
for (i = 1; i <= 4; i++)
{
for (j = 1; j <= 4 - i; j++)
printf(" ");
z = 'A';
for (j = 1; j <= 2 * i - 1; j++)
printf("%c", z++);
printf("\n");
}
return 0;
}
