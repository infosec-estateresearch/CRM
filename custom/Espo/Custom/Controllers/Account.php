<?php

namespace Espo\Custom\Controllers;

use Espo\Core\Exceptions\Forbidden;

/**
 * CRM-IDINT-001 (3.4): firms are never merged, because a merge ends by deleting
 * the source firms. The merge action is refused before it starts, so it cannot
 * move any relationship first. The signature is deliberately wide so it fits the
 * parent's whatever its parameter list.
 */
class Account extends \Espo\Modules\Crm\Controllers\Account
{
    public function postActionMerge(mixed ...$arguments): never
    {
        throw new Forbidden('Firms are never merged. Retire the duplicate or supersede it with the surviving firm.');
    }
}
